import logging

log = logging.getLogger(__name__)

# there is 10000% a better way to do this but python's logging module is a warcrime
# lord forgive me
# this whole thing is just so that I don't have to repeatedly specify variables to output as json into the logs
class ShonkyLog:
    class Decorators:
        @classmethod
        def sort(cls, unsorted_dict: dict):
            sorted_dict = dict(sorted(unsorted_dict.items()))
            return sorted_dict

        @classmethod
        def prepare_extras(cls, decorated):
            def inner(*args, **kwargs):
                extra_dict = {}

                for k, v in kwargs.items():
                    extra_dict[k] = ShonkyLog.Decorators.sort(v)

                if len(args) > 2:
                    extra_dict["other_values"] = []

                for e in args[2:]:
                    extra_dict["other_values"].append(e)

                return decorated(args[0], message=args[1], _extras=extra_dict)

            return inner

        @classmethod
        def prepare_extras_log(cls, decorated):
            def inner(*args, **kwargs):
                extra_dict = {}

                for k, v in kwargs.items():
                    extra_dict[k] = ShonkyLog.Decorators.sort(v)

                if len(args) > 3:
                    extra_dict["other_values"] = []

                for e in args[3:]:
                    extra_dict["other_values"].append(e)

                return decorated(
                    args[0], level=args[1], message=args[2], _extras=extra_dict
                )

            return inner

    def __init__(self, log: logging.Logger):
        self._log = log

    @Decorators.prepare_extras_log
    def log(
        self,
        level,
        message,
        _extras=None,
        *extras,
        **named_extras,
    ):
        self._log.log(level, message, extra=_extras)

    @Decorators.prepare_extras
    def debug(self, message, *extras, **named_extras):
        self._log.debug(message, extra=extras)

    @Decorators.prepare_extras
    def info(self, message, _extras=None, *extras, **named_extras):
        self._log.info(message, extra=_extras)

    @Decorators.prepare_extras
    def warning(self, message, _extras=None, *extras, **named_extras):
        self._log.warning(message, extra=extras)

    @Decorators.prepare_extras
    def error(self, message, _extras=None, *extras, **named_extras):
        self._log.error(message, extra=extras)

    @Decorators.prepare_extras
    def critical(self, message, _extras=None, *extras, **named_extras):
        self._log.critical(message, extra=extras)

    @Decorators.prepare_extras
    def exception(self, message, _extras=None, *extras, **named_extras):
        self._log.exception(message, extra=extras)
