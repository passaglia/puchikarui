#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Script for testing puchikarui library
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

# Copyright (c) 2014-2017, Le Tuan Anh <tuananh.ke@gmail.com>

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

########################################################################

import os
import unittest
import logging
from puchikarui import Schema

#----------------------------------------------------------------------
# Configuration
#----------------------------------------------------------------------

TEST_DIR = os.path.dirname(__file__)
SETUP_FILE = os.path.join(TEST_DIR, 'data', 'init_script.sql')
SETUP_SCRIPT = "INSERT INTO person (name, age) VALUES ('Chun', 78)"
TEST_DB = os.path.join(TEST_DIR, 'data', 'test.db')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


########################################################################

class SchemaDemo(Schema):
    def __init__(self, data_source=':memory:', setup_script=SETUP_SCRIPT, setup_file=SETUP_FILE):
        Schema.__init__(self, data_source=data_source, setup_script=setup_script, setup_file=setup_file)
        self.add_table('person', ['ID', 'name', 'age'], proto=Person, id_cols=('ID',))
        self.add_table('hobby').add_fields('pid', 'hobby')
        self.add_table('diary', ['ID', 'pid', 'text'], proto=Diary).set_id('ID').field_map(pid='ownerID', text='content')


class Diary(object):

    def __init__(self, content=''):
        """

        """
        self.ID = None
        self.owner = None
        self.ownerID = None
        self.content = content

    def __str__(self):
        return "{per} wrote `{txt}`".format(per=self.owner.name, txt=self.content)


class Person(object):
    def __init__(self, name='', age=-1):
        self.ID = None
        self.name = name
        self.age = age

    def __str__(self):
        return "#{}: {}/{}".format(self.ID, self.name, self.age)


########################################################################

class TestDemoLib(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("Setting up tests ...")
        if os.path.isfile(TEST_DB):
            logger.info("Test DB exists, removing it now")
            os.unlink(TEST_DB)

    def test_basic(self):
        print("Testing basic database actions")
        db = SchemaDemo(TEST_DB, setup_file=SETUP_FILE, setup_script=SETUP_SCRIPT)
        # We can excute SQLite script as usual ...
        db.ds.execute("INSERT INTO person (name, age) VALUES ('Chen', 15);")
        # Or use this ORM-like method
        # Test insert
        db.person.insert('Kent', 42)
        # Test select data
        persons = db.person.select(where='age > ?', values=[25], orderby='age', limit=10)
        expected = [('Ji', 28), ('Ka', 32), ('Vi', 33), ('Kent', 42), ('Chun', 78)]
        actual = [(person.name, person.age) for person in persons]
        self.assertEqual(expected, actual)
        # Test select single
        ji = db.person.select_single('name=?', ('Ji',))
        self.assertIsNotNone(ji)
        self.assertEqual(ji.age, 28)
        # Test delete
        db.person.delete(where='age > ?', values=(70,))
        chun = db.person.select_single('name=?', ('Chun',))
        self.assertIsNone(chun)

    def test_execution_context(self):
        db = SchemaDemo(":memory:")
        with db.ctx() as ctx:
            # test select
            ppl = ctx.person.select()
            self.assertEqual(len(ppl), 6)
            # test insert
            ctx.person.insert('Totoro', columns=('name',))  # insert partial data
            ctx.person.insert('Shizuka', 10)  # full record
            p = ctx.person.select_single(where='name=?', values=('Dunno',))
            self.assertIsNone(p)
            # Test update data & select single
            ctx.person.update((10,), "name=?", ("Totoro",), columns=('age',))
            totoro = ctx.person.select_single(where='name=?', values=('Totoro',))
            self.assertEqual(totoro.age, 10)
            # test updated
            ppl = ctx.person.select()
            self.assertEqual(len(ppl), 8)
            # test delete
            ctx.person.delete('age > ?', (70,))
            ppl = ctx.person.select()
            # done!
            expected = [(1, 'Ji', 28), (2, 'Zen', 25), (3, 'Ka', 32), (4, 'Anh', 15), (5, 'Vi', 33), (7, 'Totoro', 10), (8, 'Shizuka', 10)]
            actual = [(person.ID, person.name, person.age) for person in ppl]
            self.assertEqual(expected, actual)

    def test_selective_select(self):
        db = SchemaDemo()  # create a new DB in RAM
        pers = db.person.select(columns=('name',))
        names = [x.name for x in pers]
        self.assertEqual(names, ['Ji', 'Zen', 'Ka', 'Anh', 'Vi', 'Chun'])

    def test_orm_persistent(self):
        db = SchemaDemo(TEST_DB)
        bid = db.person.save(Person('Buu', 1000))
        buu = db.person.by_id(bid)
        self.assertIsNotNone(buu)
        self.assertEqual(buu.name, 'Buu')
        # insert more stuff
        db.hobby.insert(buu.ID, 'candies')
        db.hobby.insert(buu.ID, 'chocolate')
        db.hobby.insert(buu.ID, 'santa')
        hobbies = db.hobby.select('pid=?', (buu.ID,))
        self.assertEqual({x.hobby for x in hobbies}, {'candies', 'chocolate', 'santa'})
        db.hobby.delete('hobby=?', ('chocolate',))
        hobbies = db.hobby.select('pid=?', (buu.ID,))
        self.assertEqual({x.hobby for x in hobbies}, {'candies', 'santa'})

    def test_orm_with_context(self):
        db = SchemaDemo()  # create a new DB in RAM
        with db.ctx() as ctx:
            p = ctx.person.select_single('name=?', ('Anh',))
            # There is no prototype class for hobby, so a namedtuple will be generated
            hobbies = ctx.hobby.select('pid=?', (p.ID,))
            self.assertIsInstance(p, Person)
            self.assertIsInstance(hobbies[0], tuple)
            self.assertEqual(hobbies[0].hobby, 'coding')
            # insert hobby
            ctx.hobby.insert(p.ID, 'reading')
            hobbies = [x.hobby for x in ctx.hobby.select('pid=?', (p.ID,), columns=('hobby',))]
            self.assertEqual(hobbies, ['coding', 'reading'])
            # now only select the name and not the age
            p2 = ctx.person.select_single('name=?', ('Vi',), columns=('ID', 'name',))
            self.assertEqual(p2.name, 'Vi')
            self.assertEqual(p2.age, -1)
            # test updating object
            p2.name = 'Vee'
            ctx.update_object(db.person, p2, ('name',))
            p2.age = 29
            ctx.update_object(db.person, p2)
            # ensure that data was updated
            p2n = ctx.person.by_id(p2.ID)
            self.assertEqual(p2n.name, 'Vee')
            self.assertEqual(p2n.age, 29)
            self.assertEqual(p2n.ID, p2.ID)

    def test_field_mapping(self):
        db = SchemaDemo()
        with db.ctx() as ctx:
            vi = ctx.person.select_single('name=?', ('Vi',))
            ctx.diary.insert(vi.ID, 'I am NOT better than Emacs')
            diaries = ctx.diary.select('pid=?', (vi.ID,))
            for d in diaries:
                d.owner = ctx.person.by_id(d.ownerID)
                print(d)


########################################################################

def main():
    unittest.main()


if __name__ == "__main__":
    main()
