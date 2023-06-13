from . import django_settings
import datetime
import random
from ..app import create_app
import django.test
import oc_delivery_apps.dlmanager.models as dl_models
from oc_delivery_apps.checksums.controllers import CheckSumsController
import oc_delivery_apps.checksums.models as cs_models
import pytz
from .config import TestConfig
from copy import copy
import posixpath
import string
import tempfile
import os

# disable extra logging output
import logging
logging.getLogger().propagate = False
logging.getLogger().disabled = True


class ClientProviderTestSuite(django.test.TransactionTestCase):
    def __fill_db(self):
        lang_ru = dl_models.ClientLanguage(code="ru", description='ru')
        lang_ru.save()
        lang_en = dl_models.ClientLanguage(code='en', description='en')
        lang_en.save()
    
        def client_code(i):
            return 'TEST_CLIENT_{}'.format(i)
    
        for index in range(50):
            dl_models.Client.objects.create(code=client_code(index), language=
                    random.choice([lang_ru, lang_en]), is_active=True).save()
    
        for index in range(50, 60):
            dl_models.Client.objects.create(code=client_code(index), language=
                    random.choice([lang_ru, lang_en]), is_active=False).save()
    
        for index in range(10):
            dl_models.Delivery.objects.create(groupid='test.{}'.format(client_code(1)),
                                    artifactid='testartifact{}'.format(index),
                                    version=1,
                                    creation_date=(
                                        datetime.datetime.utcnow() - datetime.timedelta(days=index)).replace(
                                            tzinfo=pytz.utc),
                                    mf_delivery_files_specified='file')
    
        dl_models.Client.objects.create(code=client_code(1488), is_active=True).save()
    
    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        app = create_app(TestConfig)
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        with app.app_context():
            self.test_client = app.test_client()
        # Filling up the DB
        self.__fill_db()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def test_get_clients(self):
        response = self.test_client.get("/clients")
        self.assertEqual(response.status_code, 200)
        _actual_list = sorted(response.json)
        _expected_list = sorted(list(map(lambda x: x.code, dl_models.Client.objects.filter(is_active=True))))
        self.assertEqual(_actual_list, _expected_list)
        self.assertEqual(len(_actual_list), 51)

    def test_get_lang(self):
        def __get_lang(client_code):
            _c = dl_models.Client.objects.get(code=client_code)
            return _c.language.code if _c.language else ""

        data = ['TEST_CLIENT_1',
                'TEST_CLIENT_2']
        response = self.test_client.post('/client_lang', json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)
        _expected_langs = dict((k, __get_lang(k)) for k in data)
        _actual_langs = response.json

        for _g in _expected_langs.keys():
            self.assertEqual(_expected_langs.get(_g), _actual_langs.get(_g))

    def test_get_deliveries_in_json(self):
        response = self.test_client.post('/deliveries', json={'client': 'TEST_CLIENT_1', 'csv': False})
        _actual_list = response.json
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(_actual_list), 10)
        # first assert all attributes required are present in all deliveries

        for _d in _actual_list:
            map(lambda x: self.assertIn(x, list(_d.keys())), [
                "name", "gav", "author", "creation_date", "status", "files"])

        _expected_list = dl_models.Delivery.objects.filter(groupid__icontains='TEST_CLIENT_1')
        _expected_list = sorted(list(map(lambda x: x.gav, _expected_list)))
        _actual_list = sorted(list(map(lambda x: x.get("gav"), _actual_list)))
        self.assertEqual(_actual_list, _expected_list)
    
    def test_get_deliveries_in_csv(self):
        response = self.test_client.post('/deliveries', json={'client': 'TEST_CLIENT_1', 'csv': True})
        response_data = response.data.decode("utf-8").splitlines()
        self.assertEqual(response.status_code, 201)
        self.assertEqual("name,gav,author,creation_date,status,files", response_data.pop(0))
        _actual_list = list(map(lambda x: x.split(',').pop(1), response_data))

        for _d in dl_models.Delivery.objects.filter(groupid__contains="TEST_CLIENT_1"):
            self.assertIn(_d.gav, _actual_list)

    def test_get_deliveries_count_no_deliveries(self):
        response = self.test_client.post('/deliveries', json={'client': 'TEST_CLIENT_2', 'csv': False})
        self.assertEqual (response.status_code, 404)

    def test_get_lang_client_not_found(self):
        data = ['TEST_CLIENT_666']
        response = self.test_client.post('/client_lang', json=data)
        self.assertEqual(response.status_code, 404)

    def test_get_lang_client_lang_not_found(self):
        data = ['TEST_CLIENT_1488']
        response = self.test_client.post('/client_lang', json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual('', response.json.get(data[0]))

    def test_get_one_distinct_delivery__csv(self):
        response = self.test_client.post('/deliveries', json={'client': 'TEST_CLIENT_1', 'csv': True})
        response_data = response.data.decode("utf-8").splitlines()
        _delivery = response_data.pop(1)
        _project = _delivery.split(',').pop(0)
        response = self.test_client.post('/deliveries', json={
            'client': 'TEST_CLIENT_1', 'csv': True, 'search_params':{'project': _project}})
        self.assertEqual(_delivery, response.data.decode("utf-8").splitlines().pop())

    def test_get_one_distinct_delivery__json(self):
        response = self.test_client.post('/deliveries', json={'client': 'TEST_CLIENT_1', 'csv': False})
        response_data = response.json
        _delivery = response_data.pop()
        _project = _delivery.get("name")
        response = self.test_client.post('/deliveries', json={
            'client': 'TEST_CLIENT_1', 'csv': False, 'search_params':{'project': _project}})
        self.assertEqual(_delivery, response.json.pop())

    def test_get_deliveries_v2__no_customer(self):
        response = self.test_client.post('/v2/deliveries', json={'client': 'TEST_CLIENT_666'})
        self.assertEqual(404, response.status_code)

    def test_get_deliveries_v2__no_deliveries(self):
        response = self.test_client.post('/v2/deliveries', json={'client': 'TEST_CLIENT_3'})
        self.assertEqual(404, response.status_code)

    def test_get_deliveries_v2__custs(self):
        response = self.test_client.post('/v2/deliveries', json={'client': 'TEST_CLIENT_1'})
        self.assertEqual(201, response.status_code)
        self.assertIsInstance(response.json, list)
        _all_deliveries = response.json

        # assert all fields present
        for _d in _all_deliveries:
            map(lambda x: self.assertIn(x, _d.keys()),
                ['name', 'gav', 'author', 'creation_date', 'creation_date_mr', 'status', 'files'])

            # status must NOT be falsy
            self.assertTrue(bool(_d.get("status")))
            
            #files list must be a list
            _files = _d.get("files")
            self.assertIsInstance(_files, list)

            # all files have to be with 'path' key at least
            map(lambda x: self.assertIn('path', x.keys()), _files)

    def _random_bytes(self, len_min=None, len_max=None):
        if len_min is None:
            len_min = random.randint(0, 77)

        if len_max is None:
            len_max = random.randint(len_min, 99)

        _len = random.randint(len_min, len_max)
        return bytes(random.getrandbits(8) for _t in range(0, _len))

    def _random_text(self, len_min=None, len_max=None, add_chars=""):
        if not add_chars or not isinstance(add_chars, str):
            add_chars=""

        if len_min is None:
            len_min = random.randint(2, 7)

        if len_max is None:
            len_max = random.randint(len_min, 10)

        _len = random.randint(len_min, len_max)
        _result = ""

        while len(_result) < _len:
            _result += random.choice(string.ascii_letters + add_chars)

        return _result
        

    def test_get_deliveries_v2__distinct(self):
        ## ADDITIONAL DATA FOR THIS EXACT TEST
        _delivery_record = dl_models.Delivery.objects.filter(groupid__contains='TEST_CLIENT_1').last()
        _delivery_name = _delivery_record.delivery_name

        _csc = CheckSumsController()
        _real_gavs = ['test.group.id:test-artifact:1:bin', 'test.group.id:test-artifact:2:bin']
        _all_gavs = copy(_real_gavs) + ['test.group.id:test-artifact:3:bin']
        _real_svns = [posixpath.join('the', 'real', 'file.txt')]
        _all_svns = copy(_real_svns) + [posixpath.join('the', 'unreal', 'absent', 'file.txt')]
        _svn_root = posixpath.join('https://vcs-svn.example.com', 'svn', 'boobby', 'branches', 'billy')

        cs_models.CiTypes(code="FILE", name="File", is_standard="N", is_deliverable=False).save()
        cs_models.CiTypes(code="SVNFILE", name="File from SVN", is_standard="N", is_deliverable=True).save()
        cs_models.CsTypes(code="MD5", name="MD5 algoritm").save()
        cs_models.LocTypes(code="SVN", name="SubVersion").save()
        cs_models.LocTypes(code="NXS", name="Maven").save()

        for _f in _real_gavs:
            _t = tempfile.NamedTemporaryFile()
            _t.write(self._random_bytes())
            _t.flush()
            _t.seek(0, os.SEEK_SET)
            _csc.register_file_obj(_t, "FILE", _f, "NXS")
            _t.close()

        for _f in _real_svns:
            _t = tempfile.NamedTemporaryFile()
            _t.write(self._random_text().encode('utf-8'))
            _t.flush()
            _t.seek(0, os.SEEK_SET)
            _csc.register_file_obj(_t, "SVNFILE", posixpath.join(_svn_root, _f), "SVN", 
                    loc_revision=random.randint(1, 1000))
            _t.close()

        _delivery_record.mf_delivery_files_specified = '\n'.join(copy(_all_gavs) + copy(_all_svns))
        _delivery_record.mf_source_svn = _svn_root
        _delivery_record.mf_tag_svn = _svn_root
        _delivery_record.save()

        # get one delivery with sub-files and assert all fields carefuly
        response = self.test_client.post('/v2/deliveries', json={'client': 'TEST_CLIENT_1',
            "search_params": {"project": _delivery_name}})
        self.assertEqual(201, response.status_code)

        _delivery = response.json.pop()
        self.assertEqual(_delivery_record.gav, _delivery.get("gav"))

        # assert files are those we specified there
        _all_files = copy(_all_svns) + copy(_all_gavs)
        for _file in _delivery.get("files"):
            self.assertTrue(bool(_file.get("path")))
            self.assertIn(_file.get("path"), _all_files)

            if _file.get("path") in _real_gavs:
                self.assertEqual(_file.get("location_type"), "NXS")
                self.assertEqual(_file.get("full_path"), _file.get("path"))
                self.assertEqual(_file.get("citype"), "FILE")
                self.assertEqual(_file.get("citype_desc"), "File")
                continue

            if _file.get("path") in _real_svns:
                self.assertEqual(_file.get("location_type"), "SVN")
                self.assertEqual(_file.get("full_path"), posixpath.join(_svn_root, _file.get("path")))
                self.assertEqual(_file.get("citype"), "SVNFILE")
                self.assertEqual(_file.get("citype_desc"), "File from SVN")
                continue

            self.assertNotIn("full_path", _file.keys())
            self.assertNotIn("location_type", _file.keys())
            self.assertNotIn("citype", _file.keys())
            self.assertNotIn("citype_desc", _file.keys())


    def test_get_deliveries_v2__date_range(self):
        # note that all deliveries creation date is shifted in 'setUp' in number of days
        # so we can easilly found one delivery made 'yesterday'
        _day_to_search = (datetime.datetime.utcnow() - datetime.timedelta(days=1))
        _day_to_search_s = _day_to_search.strftime("%d-%m-%Y")
        _day_to_check = _day_to_search.strftime("%Y%m%d")
        _response = self.test_client.post('/v2/deliveries', json={'client': 'TEST_CLIENT_1',
            "search_params": {"date_range_before": _day_to_search_s, "date_range_after": _day_to_search_s}})
        self.assertEqual(_response.status_code, 201)

        # since 'creation_date' is shifted on the whole day, then we have to obtain one first delivery
        self.assertEqual(len(_response.json), 1)
        _delivery = _response.json.pop()
        self.assertTrue(_delivery.get('creation_date_mr').startswith(_day_to_check))
