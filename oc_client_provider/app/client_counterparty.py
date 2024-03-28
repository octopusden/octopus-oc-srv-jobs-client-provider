import yaml
import os
import logging

class ClientCounterparty(object):
    def __init__(self):
        __enabled = bool(os.getenv("COUNTERPARTY_ENABLED", "").lower() in ["y", "yes", "true"])

        if not __enabled:
            logging.debug("Counterparty is disabled")
            return

        self.__counterparty_path = os.path.abspath(
                os.getenv("COUNTERPARTY_PATH") or 'client_counterparties.yml')

        logging.debug("Counerparty configuration path: [%s]" % self.__counterparty_path)

    def client_counterparty (self, client_code):
        """
        Get counterparty by client code
        :param client_code: client code
        :return: client counterparty
        """
        if not hasattr(self, "_ClientCounterparty__counterparty_path") or not self.__counterparty_path:
            logging.debug("Counterparty is disabled, returning empty string")
            return ''

        with open(self.__counterparty_path) as _stream:
            _data = yaml.load (_stream, Loader=yaml.Loader)

        # fix possible None in "data" loaded. Example - when source YAML is empty
        if not _data:
            logging.debug("Counterparty configuration is empty, returning empty string")
            return ''

        _result = _data.get(client_code)

        if not _result:
            logging.debug("Counterparty not found for [%s], returning empty string" % client_code)
            return ''

        logging.debug("Returning [%s] for client [%s]" % (_result, client_code))
        return _result
