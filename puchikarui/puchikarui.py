#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Mini SQLite ORM engine
Latest version can be found at https://github.com/letuananh/puchikarui

References:
    Python documentation:
        https://docs.python.org/
    Python unittest
        https://docs.python.org/3/library/unittest.html
    --
    argparse module:
        https://docs.python.org/3/howto/argparse.html
    PEP 257 - Python Docstring Conventions:
        https://www.python.org/dev/peps/pep-0257/

@author: Le Tuan Anh <tuananh.ke@gmail.com>
'''


# Copyright (c) 2014, Le Tuan Anh <tuananh.ke@gmail.com>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

__author__ = "Le Tuan Anh <tuananh.ke@gmail.com>"
__copyright__ = "Copyright 2017, puchikarui"
__credits__ = []
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Le Tuan Anh"
__email__ = "<tuananh.ke@gmail.com>"
__status__ = "Prototype"

#-------------------------------------------------------------

import os
import sqlite3
import collections
import logging

#-------------------------------------------------------------
# CONFIGURATION
#-------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

#-------------------------------------------------------------
# PuchiKarui
# A minimalist SQLite wrapper library for Python which supports ORM features too.
#-------------------------------------------------------------


# A table schema
class Table:
    def __init__(self, name, columns, data_source=None, proto=None, id_cols=None):
        self.name = name
        self.columns = columns
        self._data_source = data_source
        self._proto = proto
        self._id_cols = id_cols
        try:
            collections.namedtuple(self.name, self.columns, verbose=False, rename=False)
        except Exception as ex:
            logger.warning("WARNING: Bad database design detected (Table: %s (%s)" % (name, columns))
        self.template = collections.namedtuple(self.name, self.columns, rename=True)

    def __str__(self):
        return "Table: %s - Cols: %s" % (self.name, self.columns)

    def to_table(self, row_tuples, columns=None):
        if not row_tuples:
            raise ValueError("Invalid row_tuples")
        else:
            if self._proto:
                return [self.to_obj(x, columns) for x in row_tuples]
            if columns:
                new_tuples = collections.namedtuple(self.name, columns, rename=True)
                return [self.to_row(x, new_tuples) for x in row_tuples]
            else:
                return [self.to_row(x) for x in row_tuples]

    def to_row(self, row_tuple, template=None):
        if template:
            return template(*row_tuple)
        else:
            return self.template(*row_tuple)

    def to_obj(self, row_tuple, columns=None):
        # fall back to row_tuple
        if not self._proto:
            return self.to_row(row_tuple)
        # else create objects
        if not columns:
            columns = self.columns
        new_obj = to_obj(self._proto, dict(zip(columns, row_tuple)), *columns)
        # assign values
        return new_obj

    def select_single(self, where=None, values=None, orderby=None, limit=None, columns=None, exe=None):
        ''' Select a single row
        '''
        result = self.select(where, values, orderby, limit, columns, exe)
        if result and len(result) > 0:
            return result[0]
        else:
            return None

    def select(self, where=None, values=None, orderby=None, limit=None, columns=None, exe=None):
        if exe is not None:
            return exe.select_record(self, where, values, orderby=orderby, limit=limit, columns=columns)
        else:
            with self._data_source.open() as exe:
                return exe.select_record(self, where, values, orderby=orderby, limit=limit, columns=columns)

    def ctx(self, exe):
        return TableContext(self, exe)

    def insert(self, *values, columns=None, exe=None):
        if exe is not None:
            return self.ctx(exe).insert(*values, columns=columns)
        else:
            with self._data_source.open() as exe:
                return self.ctx(exe).insert(*values, columns=columns)

    def delete(self, where=None, values=None, exe=None):
        if exe is not None:
            return self.ctx(exe).delete(where=where, values=values)
        else:
            with self._data_source.open() as exe:
                return self.ctx(exe).delete(where=where, values=values)

    def delete_obj(self, obj, exe=None):
        if exe is not None:
            return self.ctx(exe).delete_obj(obj)
        else:
            with self._data_source.open() as exe:
                return self.ctx(exe).delete_obj()

    def update(self, new_values, where='', where_values=None, columns=None, exe=None):
        if exe is not None:
            return self.ctx(exe).update(new_values, where, where_values, columns)
        else:
            with self._data_source.open() as exe:
                return self.ctx(exe).update(new_values, where, where_values, columns)

    def by_id(self, *args, columns=None, exe=None):
        if exe is not None:
            return self.ctx(exe).by_id(*args, columns=columns)
        else:
            with self._data_source.open() as exe:
                return self.ctx(exe).by_id(*args, columns=columns)

    def save(self, obj, columns=None, exe=None):
        if exe is not None:
            return self.ctx(exe).save(obj, columns)
        else:
            with self._data_source.open() as exe:
                return self.ctx(exe).save(obj, columns)


class DataSource:

    def __init__(self, db_path, setup_script=None, setup_file=None, auto_commit=True, schema=None):
        self._filepath = db_path
        self._setup_script = setup_script
        self.auto_commit = auto_commit
        if setup_file is not None:
            with open(setup_file, 'r') as scriptfile:
                logger.debug("Setup script file provided: {}".format(setup_file))
                self._setup_file = scriptfile.read()
        else:
            self._setup_file = None
        self.schema = schema

    @property
    def path(self):
        return self._filepath

    def open(self, auto_commit=None, schema=None):
        ''' Create a context to execute queries '''
        if not schema:
            schema = self.schema
        ac = auto_commit if auto_commit is not None else self.auto_commit
        exe = ExecutionContext(self.path, schema=schema, auto_commit=ac)
        # setup DB if required
        if not os.path.isfile(self.path) or os.path.getsize(self.path) == 0:
            logger.warning("DB does not exist. Setup is required.")
            # run setup script
            if self._setup_file is not None:
                exe.cur.executescript(self._setup_file)
            if self._setup_script is not None:
                exe.cur.executescript(self._setup_script)
        return exe

    # Helper functions
    def execute(self, query, params=None):
        with self.open() as exe:
            return exe.execute(query, params)

    def executescript(self, query):
        with self.open() as exe:
            return exe.executescript(query)

    def executefile(self, file_loc):
        with self.open() as exe:
            return exe.executefile(file_loc)


# This was adopted from chirptext
def update_data(source, target, *fields, **field_map):
    source_dict = source.__dict__ if hasattr(source, '__dict__') else source
    target_dict = target.__dict__ if hasattr(target, '__dict__') else target
    if not fields:
        fields = source_dict.keys()
    for f in fields:
        target_f = f if f not in field_map else field_map[f]
        target_dict[target_f] = source_dict[f]


def to_obj(cls, obj_data=None, *fields, **field_map):
    ''' prioritize obj_dict when there are conficts '''
    obj_dict = obj_data.__dict__ if hasattr(obj_data, '__dict__') else obj_data
    if not fields:
        fields = obj_dict.keys()
    # obj_kwargs = {}
    # for k in fields:
    #     f = k if k not in field_map else field_map[k]
    #     obj_kwargs[f] = obj_dict[k]
    obj = cls()
    update_data(obj_dict, obj, *fields, **field_map)
    return obj


class QueryBuilder(object):

    ''' Default query builder '''
    def __init__(self, schema):
        self.schema = schema

    def build_select(self, table, where=None, orderby=None, limit=None, columns=None):
        query = []
        if not columns:
            columns = table.columns
        query.append("SELECT ")
        query.append(','.join(columns))
        query.append(" FROM ")
        query.append(table.name)
        if where:
            query.append(" WHERE ")
            query.append(where)
        if orderby:
            query.append(" ORDER BY ")
            query.append(orderby)
        if limit:
            query.append(" LIMIT ")
            query.append(str(limit))
        return ''.join(query)

    def build_insert(self, table, values, columns=None):
        ''' Insert an active record into DB and return lastrowid if available '''
        if not columns:
            columns = table.columns
        if len(values) < len(columns):
            column_names = ','.join(columns[-len(values):])
        else:
            column_names = ','.join(columns)
        query = "INSERT INTO %s (%s) VALUES (%s) " % (table.name, column_names, ','.join(['?'] * len(values)))
        return query

    def build_update(self, table, where='', columns=None):
        if columns is None:
            columns = table.columns
        set_fields = []
        for col in columns:
            set_fields.append("{c}=?".format(c=col))
        if where:
            query = 'UPDATE {t} SET {sf} WHERE {where}'.format(t=table.name, sf=', '.join(set_fields), where=where)
        else:
            query = 'UPDATE {t} SET {sf}'.format(t=table.name, sf=', '.join(set_fields))
        return query

    def build_delete(self, table, where=None):
        if where:
            query = "DELETE FROM {tbl} WHERE {where}".format(tbl=table.name, where=where)
        else:
            query = "DELETE FROM {tbl}".format(tbl=self.name)
        return query


class TableContext(object):
    def __init__(self, table, context):
        self._table = table
        self._context = context

    def select(self, where=None, values=None, **kwargs):
        return self._context.select_record(self._table, where, values, **kwargs)

    def select_single(self, where=None, values=None, **kwargs):
        result = self._context.select_record(self._table, where, values, **kwargs)
        if result and len(result) > 0:
            return result[0]
        else:
            return None

    def insert(self, *values, columns=None):
        return self._context.insert_record(self._table, values, columns)

    def update(self, new_values, where='', where_values=None, columns=None):
        return self._context.update_record(self._table, new_values, where, where_values, columns)

    def delete(self, where=None, values=None):
        return self._context.delete_record(self._table, where, values)

    def by_id(self, *args, columns=None):
        return self._context.select_object_by_id(self._table, args, columns)

    def save(self, obj, columns=None):
        existed = True
        for i in self._table._id_cols:
            existed = existed and getattr(obj, i)
        if existed:
            # update
            return self._context.update_object(self._table, obj, columns)
        else:
            # insert
            return self._context.insert_object(self._table, obj, columns)

    def delete_obj(self, obj):
        return self._context.delete_object(self._table, obj)


class ExecutionContext(object):
    ''' Create a context to work with a schema which closes connection when destroyed
    '''
    def __init__(self, path, schema, auto_commit=True):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self.schema = schema
        self.auto_commit = auto_commit

    def commit(self):
        if self.conn:
            try:
                self.conn.commit()
            except Exception as e:
                logger.exception("Cannot commit changes. e = %s" % e)

    def select_record(self, table, where=None, values=None, orderby=None, limit=None, columns=None):
        ''' Support these keywords where, values, orderby, limit and columns'''
        query = self.schema.query_builder.build_select(table, where, orderby, limit, columns)
        return table.to_table(self.execute(query, values), columns=columns)

    def insert_record(self, table, values, columns=None):
        query = self.schema.query_builder.build_insert(table, values, columns)
        self.execute(query, values)
        return self.cur.lastrowid

    def update_record(self, table, new_values, where='', where_values=None, columns=None):
        query = self.schema.query_builder.build_update(table, where, columns)
        return self.execute(query, new_values + where_values if where_values else new_values)

    def delete_record(self, table, where=None, values=None):
        query = self.schema.query_builder.build_delete(table, where)
        logger.debug("Executing: {q} | values={v}".format(q=query, v=values))
        return self.execute(query, values)

    def select_object_by_id(self, table, ids, columns=None):
        where = ' AND '.join(['{c}=?'.format(c=c) for c in table._id_cols])
        results = self.select_record(table, where, ids, columns=columns)
        if results:
            return results[0]
        else:
            return None

    def insert_object(self, table, obj_data, columns=None):
        if not columns:
            columns = table.columns
        values = tuple(getattr(obj_data, colname) for colname in columns)
        self.insert_record(table, values, columns)
        return self.cur.lastrowid

    def update_object(self, table, obj_data, columns=None):
        where = ' AND '.join(['{c}=?'.format(c=c) for c in table._id_cols])
        where_values = tuple(getattr(obj_data, colname) for colname in table._id_cols)
        if not columns:
            columns = table.columns
        new_values = tuple(getattr(obj_data, colname) for colname in columns)
        self.update_record(table, new_values, where, where_values, columns)

    def delete_object(self, table, obj_data):
        where = ' AND '.join(['{c}=?'.format(c=c) for c in table._id_cols])
        where_values = tuple(getattr(obj_data, colname) for colname in table._id_cols)
        self.delete_record(table, where, where_values)

    def execute(self, query, params=None):
        # Try to connect to DB if not connected
        try:
            if params:
                return self.cur.execute(query, params)
            else:
                return self.cur.execute(query)
        except:
            logger.exception('Invalid query. q={}, p={}'.format(query, params))
            raise

    def executescript(self, query):
        return self.cur.executescript(query)

    def executefile(self, file_loc):
        with open(file_loc, 'r') as script_file:
            script_text = script_file.read()
            self.executescript(script_text)

    def close(self):
        try:
            if self.conn is not None:
                if self.auto_commit:
                    self.commit()
                self.conn.close()
        except:
            logger.exception("Error while closing connection")
        finally:
            self.conn = None

    def __getattr__(self, name):
        if not self.schema or name not in self.schema._tables:
            raise AttributeError('Attribute {} does not exist'.format(name))
        else:
            tbl = getattr(self.schema, name)
            ctx = TableContext(tbl, self)
            setattr(self, name, ctx)
            return getattr(self, name)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        try:
            self.close()
        except Exception as e:
            logger.exception("Error was raised while closing DB connection. e = %s" % e)


class Schema(object):
    ''' Contains schema definition of a database
    '''
    def __init__(self, data_source, setup_script=None, setup_file=None, auto_commit=True):
        if type(data_source) is DataSource:
            self.data_source = data_source
        else:
            self.data_source = DataSource(data_source, setup_script=setup_script, setup_file=setup_file, auto_commit=auto_commit, schema=self)
        self.auto_commit = auto_commit
        self._tables = {}
        self.query_builder = QueryBuilder(self)

    def add_table(self, name, columns, id_cols=None, proto=None, alias=None):
        tbl_obj = Table(name, columns, self.data_source, id_cols=id_cols, proto=proto)
        setattr(self, name, tbl_obj)
        self._tables[name] = tbl_obj
        if alias:
            setattr(self, alias, tbl_obj)
            self._tables[alias] = tbl_obj

    @property
    def ds(self):
        return self.data_source

    def ctx(self):
        ''' Create a new execution context '''
        return self.ds.open(schema=self)


#-------------------------------------------------------------
# Main
#-------------------------------------------------------------

def main():
    print("PuchiKarui is a Python module, not an application")


#-------------------------------------------------------------
if __name__ == "__main__":
    main()
