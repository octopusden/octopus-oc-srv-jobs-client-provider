import pytz
import logging
from datetime import datetime
from itertools import chain
import posixpath


## NOTE: imports of django-related things are done in the methods where they necessary
##       in case of global import 'unittest discover' command fails because Django is not configured yet

class ClientGetter:
    """
    Checks artifacts existence in the DB using their GAVs
    """

    def get_clients(self):
        """
        Returns list of active clients
        :return list: list of strings client codes or empty list
        """
        logging.debug("Reached get_clients")

        try:
            # get filtered records from DB, exclude those who does not have client code filled
            from oc_delivery_apps.dlmanager.models import Client
            records = Client.objects.filter(is_active=True)
            records = list(map(lambda x: x.code, records))
            records = list(filter(lambda x: bool(x), records))
        except Client.DoesNotExist as err:
            logging.exception(err)
            return list()

        return records

    def get_client_data(self, client_id):
        """
        Returns client data by id
        :param int client_id: client id (primary key)
        :return dict: client data or None
        """
        logging.debug('Reached get_client_data')
        logging.debug('Requested code for id [%s]' % client_id)

        # get data for specific client, fiter by id

        try:
            from oc_delivery_apps.dlmanager.models import Client
            record = Client.objects.get(id=client_id)

            if not record:
                # this should never happen since DoesNotExist is usually raised for this
                return None

        except Client.DoesNotExist as _e:
            logging.exception(_e)
            return None

        logging.debug('Fetched [%s]' % record)

        # all fields are not required to be filled by models, so do not forget to filter 'language'
        # since this is the only place where exception may be raised

        res = { 'code': record.code,
                'country': record.country,
                'language': record.language.code if record.language else ''}

        logging.debug("Returning '%s'" % str(res))

        return res

    def get_client_lang_list(self, client_code_list):
        """
        Converts list of client codes to dict client_code: client_lang
        Letters case in cdes are not controlled
        :param list client_code_list: list of CDT client codes
        :return dict: {client_code: client_lang}
        """
        try:
            from oc_delivery_apps.dlmanager.models import Client
            client_records = Client.objects.filter(code__in=client_code_list)
            client_records = list(filter(lambda x: bool(x) and bool(x.code), client_records))
            client_records = dict((x.code, x.language.code if x.language else '') for x in client_records)
        except Client.DoesNotExist as e:
            logging.exception(e)
            return dict()

        return client_records

    def _resolve_search_components(self, code):
        """ 
        Determines whether single CiType or whole CiTypeGroup was requested 
        :param str code: CiType.code or CiTypeGroup.code 
        :return: list of Component (one for CiType or multiple for CiTypeGroup)
        """
        logging.debug('Reached _resolve_search_components')
        logging.debug('The code is [%s]' % code)
        from oc_delivery_apps.checksums.models import CiTypeGroups, CiTypeIncs, CiTypes

        try:
            group = CiTypeGroups.objects.get(code=code)
            components_codes = [inclusion.ci_type.code for inclusion in CiTypeIncs.objects.filter(ci_type_group=group)]
        except CiTypeGroups.DoesNotExist:
            logging.debug('No ci_type_group found for code [%s].' % (code))
            component_codes = None

        if component_codes is None:
            # no group - search for type directly
            # absence of type is checked below
            component_codes = [code]

        from oc_delivery_apps.checksums.Component import Component
        components = list(map(lambda x: Component(x), 
            CiTypes.objects.filter(code__in=components_codes)))

        if not components:
            # empty list
            logging.warning("No ci_types found for code [%s]." % code)
            return None

        return components

    def __fix_date_range_search_params(self, search_params):
        """
        This conversion is added for old Django compatibility.
        There was an argument renaming while migration from v2 to v3:
        "date_range_0", "date_range_1" --> "date_range_after", "date_range_before"
        Here we do some replacement for older version compatibility
        Replacement for our "improvement" is done here also (see app.py):
        "date_from", "date_to" -> "date_range_0", "date_range_1"
        :param dict search_params: dict to fix
        :return dict: search params fixed
        """
        _date_keys_correspondence = {
                "date_range_0": "date_range_after",
                "date_range_1": "date_range_before",
                "date_from": "date_range_after",
                "date_to": "date_range_before"}

        for k, v in  _date_keys_correspondence.items():
            if k not in search_params.keys():
                continue

            if v in search_params.keys():
                # preferre new-style formatted value, exclude old one and ignore
                logging.warning("Ignoring search parameter [%s], using [%s] only" % (k, v))
                del(search_params[k])
                continue

            logging.warning("Converting search parameter [%s] to new-style [%s]" % (k, v))
            search_params[v] = search_params[k]
            del(search_params[k])


        return search_params

    def _process_search_params(self, client_code, search_params, timezone):
        # TODO: split this monstreous method to short separate steps and apply unit-tests for them
        """
        Process search params into DB query
        :param str client_code: client code
        :param dict search_params: search filters for current client deliveries
        :param str timezone: str
        :return: Django Queryset for the given parameters
        """
        logging.info('Reached _process_search_params')
        logging.debug('Client code: [%s]' % client_code)
        logging.debug('Search Params: %s' % str(search_params))

        db_query = dict()

        if search_params:
            # Common fields mapping for both FILE and Component search

            search_params_mapping_to_db = {
                "created_by": "mf_delivery_author__contains",
                "comment": "mf_delivery_comment__contains"
            }

            component_code = search_params.get('component_0')

            logging.debug('Component code: [%s]' % component_code)
            db_query = dict((search_params_mapping_to_db[key], value) for key, value in search_params.items(
                        ) if key in search_params_mapping_to_db.keys() and value)
            logging.debug('Common db_query: %s' % str(db_query))

            # Adding files/components filters to the query
            if component_code == 'FILE':
                _c1 = search_params.get("component_1")

                if _c1:
                    db_query.update({"mf_delivery_files_specified__contains": _c1})

                logging.debug('Updated db_query for FILE: %s' % str(db_query))

            elif component_code:
                logging.debug('Not a "FILE" requested as component, searching using the type given')
                components = self._resolve_search_components(component_code)

                if components:
                    _component_version = search_params.get('component_1') or ""
                    templates = list(chain(*[component.get_templates(_component_version)
                        for component in components]))
                    combined_regex = '|'.join(templates)
                    logging.debug('Regexp to search for [%s] (v. [%s]): %s' % (
                        component_code, _component_version, combined_regex))

                    if combined_regex:
                        # regexps for all types requested may be absent in the database,
                        # so 'combined regex' may be empty even if 'components' are not
                        db_query.update({"mf_delivery_files_specified__iregex": combined_regex})

                logging.debug('Updated db_query: %s' % str(db_query))

            # Adding flags to the query
            flags_mapping_to_db = {
                "is_uploaded": "flag_uploaded",
                "is_approved": "flag_approved",
                "is_failed": "flag_failed"
            }

            for key, value in search_params.items():
                # here is a very big portal form transformation with hardcoded values
                # TODO: rid of these correspondence tables

                if not key.startswith('is_'):
                    continue
                if value not in ['2', '3']:
                    continue
                if key not in flags_mapping_to_db.keys():
                    continue

                db_value = bool(value == '2')
                logging.debug('Adding [%s]:[%s] query' % (flags_mapping_to_db[key], db_value))
                db_query.update({flags_mapping_to_db[key]: db_value})

            # Adding time range fields to the query
            # TODO: change date format to more common 'YYYY-MM-DD'
            # NOTE 2: in recent Django there was an argumnent substitution for date search.
            # Fixing it in separate method
            # TODO: rid of this after all sub-services will be switched to new format
            search_params = self.__fix_date_range_search_params(search_params)

            date_range_requested = dict((key, pytz.timezone(timezone).localize(datetime.strptime(
                value, "%d-%m-%Y"))) for key, value in search_params.items(
                    ) if key in ["date_range_after", "date_range_before"] and value)

            if date_range_requested:
                logging.debug('Date range requested: [%s]' % date_range_requested)
                start_date = date_range_requested.get('date_range_after')
                end_date = date_range_requested.get('date_range_before')

                if not end_date:
                    end_date = datetime.now(pytz.timezone(timezone))

                if not start_date:
                    start_date = datetime.min.replace(tzinfo=pytz.timezone(timezone))

                # By default the time is set to 00:00 which excludes the whole end day from the search
                end_date = end_date.replace(hour=23, minute=59, second=59)

                db_query.update({"creation_date__range": [start_date, end_date]})


        # Adding filtration by client_code
        db_query.update({"groupid__endswith": client_code})

        logging.debug("Final query: %s" % str(db_query))

        from oc_delivery_apps.dlmanager.models import Delivery
        search_queryset = Delivery.objects.filter(**db_query)

        # enhanced queryset workaround for 'project' parameter (delivery_name lambda property)
        # necessary since Django rids of 'lambda' properties comparison directly, so this will not work:
        #   db_query.update({"delivery_name__icontains": _prj})

        _prj = search_params.get("project")
        if _prj:
            from django.db.models import F, Value, CharField
            from django.db.models.functions import Concat
            fullname_annotation = Concat(F("artifactid"), Value("-"), F("version"), output_field=CharField())
            enhanced_search_queryset = search_queryset.annotate(annotated_delivery_name=fullname_annotation)
            search_queryset = enhanced_search_queryset.filter(annotated_delivery_name__icontains=_prj)

        return search_queryset

    def get_deliveries(self, client_code, search_params, timezone):
        """
        Gathering deliveries for specified client
        :param str client_code: client code
        :param dict search_params: search filters
        :param str timezone: timezone
        :return tuple: (list of delivery objects, error message)
        """
        logging.info('Looking for [%s] deliveries with search params: %s' % (client_code, str(search_params)))

        try:
            delivery_records = self._process_search_params(client_code, search_params, timezone)
            logging.info('Found %d records for client [%s]' % (delivery_records.count(), client_code))
            if not delivery_records:
                return list(), None

            # TODO: change date format to YYYY-MM-DD HH24:MM:SS (traditionally used in other places)
            delivery_records = list(map(lambda x: {
                        'name': x.delivery_name,
                        'gav': x.gav,
                        'author': x.mf_delivery_author,
                        'creation_date': x.creation_date.astimezone(
                            tz=pytz.timezone(timezone)).strftime("%b %d %Y %H:%M:%S"),
                        'status': x.comment,
                        'files': ';'.join(x.mf_delivery_files_specified.split('\n'))}, delivery_records))

            return delivery_records, None

        except Exception as e:
            logging.exception(e)
            error = str(e)

        return list(), error

    def get_deliveries_v2(self, client_code, search_params, timezone):
        """
        Gathering deliveries for specified client
        :param str client_code: client code
        :param dict search_params: search filters
        :param str timezone: timezone
        :return tuple: list of delivery objects, error message
        """
        logging.info('V2: Looking for [%s] deliveries with search params: %s' %(client_code, str(search_params)))

        try:
            delivery_records = self._process_search_params(client_code, search_params, timezone)
            logging.info('Found %d records for customer [%s]' % (delivery_records.count(), client_code))

            if not delivery_records:
                return list(), None

            delivery_records = list(map(lambda x: {
                        'name': x.delivery_name,
                        'gav': x.gav,
                        'author': x.mf_delivery_author,
                        'creation_date': x.creation_date.astimezone(
                            tz=pytz.timezone(timezone)).strftime("%b %d %Y %H:%M:%S"),
                        'creation_date_mr': x.creation_date.astimezone(
                            tz=pytz.timezone(timezone)).strftime("%Y%m%d%H%M%S"),
                        'status': x.business_status.description if x.business_status else x.get_flags_description(),
                        'files': self._get_files(x)}, delivery_records))

            return delivery_records, None

        except Exception as e:
            logging.exception(e)
            error = str(e)

        return list(), error

    def _get_files(self, delivery):
        """
        Convert string field with delivery files to a list of dictionaries with files details
        :param dlmanager.models.Delivery delivery: delivery record
        :return list(dict()): list of dictionaries with files details
        """
        logging.debug("Reached _get_files, Delivery id is [%d]" % delivery.id)

        if not isinstance(delivery.mf_delivery_files_specified, str) \
                or not delivery.mf_delivery_files_specified.strip():
            logging.debug("No files for delivery id=[%d], returning empty list" % delivery.id)
            return list()

        files = delivery.mf_delivery_files_specified.strip().replace('\n', ';').split(';')
        # get rid of empty lines
        files = list(map(lambda x: x.strip(), files))
        files = list(filter(lambda x: bool(x), files))

        if not files:
            logging.debug("Empty list of files for delivery [%d], returning it", delivery.id)
            return list()

        logging.debug("Parsed [%s] records" % len(files))
        svn_prefix = delivery.mf_tag_svn

        files = list(map(lambda x: self._get_file_record(x, delivery), files))
        logging.debug("Returning list of file records: %s" % str(files))
        return files

    def _get_file_record(self, path, delivery):
        """
        Get single file record dictionary
        :param str path: path from filelist (SVN or gav)
        :param dlmanager.models.Delivery delivery: delivery record
        :return dict: file-record as dictionary with details
        """
        logging.debug("Reached _get_file_record")
        logging.debug("path: [%s]" % path)
        logging.debug("delivery: [%s]" % delivery)
        from oc_delivery_apps.checksums.models import Locations

        # search in Locations first
        _full_path = posixpath.sep.join([delivery.mf_tag_svn, path]) if posixpath.sep in path else path
        _r = Locations.history.filter(path=_full_path, history_date__lte=delivery.creation_date).order_by(
                'history_date')

        if not _r.count():
            logging.debug("No records in historical locations table, searching locations")
            _r = Locations.objects.filter(path=_full_path).order_by('input_date')

        if not _r.count():
            logging.debug("No records in any table, returning just path")
            return {"path": path}

        # getting latest record
        _r = _r.last()
        _result = {
                "citype": _r.file.ci_type.code,
                "citype_desc" : _r.file.ci_type.name,
                "location_type": _r.loc_type.code,
                "path": path,
                "full_path": _full_path}

        logging.debug("About to return: %s" % _result)
        return _result
