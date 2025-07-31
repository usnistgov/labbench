import datetime
import io
import logging
import logging.handlers
import socket
import sys
import time
import typing

from pathlib import Path

from . import _device as core
from . import paramattr as attr
from . import util

if typing.TYPE_CHECKING:
    from dulwich import porcelain, repo
    import json
    import pandas as pd
    import pip
    import smtplib
    import traceback
    import email.mime.text as mime_text
else:
    json = util.lazy_import('json')
    mime_text = util.lazy_import('email.mime.text')
    pd = util.lazy_import('pandas')
    pip = util.lazy_import('pip')
    porcelain = util.lazy_import('dulwich.porcelain')
    repo = util.lazy_import('dulwich.repo')
    smtplib = util.lazy_import('smtplib')
    traceback = util.lazy_import('traceback')

__all__ = ['Host', 'Email']


def find_repo_in_parents(path: Path) -> 'repo.Repo':
    """find a git repository in path, or in the first parent to contain one"""
    path = Path(path).absolute()

    try:
        return repo.Repo(str(path))
    except repo.NotGitRepository as ex:
        if not path.is_dir() or path.parent is path:
            raise

        try:
            return find_repo_in_parents(path.parent)
        except repo.NotGitRepository:
            ex.args = ex.args[0] + ' (and parent directories)'
            raise ex


class LogStreamBuffer:
    def __init__(self):
        self._value = ''

    def write(self, msg):
        self._value = self._value + msg
        return len(msg)

    def read(self):
        ret, self._value = self._value, ''
        return ret

    def flush(self):
        pass


class LogStderr(core.Device):
    """This "Device" logs a copy of messages on sys.stderr while connected."""

    log = ''

    def open(self):
        self._stderr, self._buf, sys.stderr = sys.stderr, io.StringIO(), self

    def close(self):
        if self.isopen:
            sys.stderr = self._stderr
            self.log = self._buf.getvalue()
            self._buf.close()

    def write(self, what):
        self._stderr.write(what)
        self._buf.write(what)

    def flush(self):
        try:
            self._buf.flush()
            self.log += self._buf.getvalue()
        except ValueError:
            pass


class Email(core.Device):
    """Sends a notification message on disconnection. If an exception
    was thrown, this is a failure subject line with traceback information
    in the main body. Otherwise, the message is a success message in the
    subject line. Stderr is also sent.
    """

    resource: str = attr.value.NetworkAddress(
        default='smtp.nist.gov', kw_only=False, help='smtp server to use', cache=True
    )
    port: int = attr.value.int(default=25, min=1, help='TCP/IP port', cache=True)
    sender: str = attr.value.str(
        default='myemail@nist.gov', help='email address of the sender', cache=True
    )
    recipients: list = attr.value.list(
        default=['myemail@nist.gov'],
        help='list of email addresses of recipients',
        cache=True,
    )

    success_message: str = attr.value.str(
        default='Test finished normally',
        allow_none=True,
        help='subject line for test success emails (None to suppress the emails)',
        cache=True,
    )

    failure_message: str = attr.value.str(
        default='Exception ended test early',
        allow_none=True,
        help='subject line for test failure emails (None to suppress the emails)',
        cache=True,
    )

    def _send(self, subject, body):
        sys.stderr.flush()
        self.backend.flush()

        msg = mime_text.MIMEText(body, 'html')
        msg['From'] = self.sender
        msg['Subject'] = subject
        msg['To'] = ', '.join(self.recipients)
        self.server = smtplib.SMTP(self.resource, self.port)

        try:
            self.server.sendmail(self.sender, self.recipients, msg.as_string())
        finally:
            self.server.quit()

    def open(self):
        self.backend = LogStderr()
        self.backend.open()

    def close(self):
        if self.isopen:
            self.backend.close()
            util.sleep(1)
            self.send_summary()

    def send_summary(self):
        """Send the email containing the final property trait of the test."""
        exc = sys.exc_info()

        if exc[0] is KeyboardInterrupt:
            return

        if exc != (None, None, None):
            if self.failure_message is None:
                return
            subject = self.failure_message
            message = (
                '<b>Exception</b>\n'
                + '<font face="Courier New, Courier, monospace">'
                + traceback.format_exc()
                + '</font>'
            )
        else:
            if self.success_message is None:
                return
            subject = self.success_message
            message = ''

        if len(self.backend.log) > 0:
            message = (
                message
                + '\n\n<b>Standard error</b>\n'
                + '<font face="Courier New, Courier, monospace">'
                + self.backend.log
                + '</font>'
            )

        self._send(subject, message.replace('\n', '<br>'))

        return subject, message


class JSONFormatter(logging.Formatter):
    _last = []

    def __init__(self):
        super().__init__(style='{')
        self.t0 = time.time()
        self.first = True

    @staticmethod
    def json_serialize_dates(obj):
        """JSON serializer for objects not serializable by default json code"""

        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        raise TypeError(f'Type {type(obj).__qualname__} not serializable')

    def format(self, rec: logging.LogRecord):
        """Return a YAML string for each logger record"""

        if isinstance(rec.args, dict):
            kwargs = rec.args
        else:
            kwargs = {}

        msg = dict(
            message=rec.msg,
            time=datetime.datetime.fromtimestamp(rec.created),
            elapsed_seconds=rec.created - self.t0,
            level=rec.levelname,
            object=getattr(rec, 'object', None),
            object_log_name=getattr(rec, 'owned_name', None),
            source_file=rec.pathname,
            source_line=rec.lineno,
            process=rec.process,
            thread=rec.threadName,
            **kwargs,
        )

        if rec.threadName != 'MainThread':
            msg['thread'] = rec.threadName

        etype, einst, exc_tb = sys.exc_info()
        if etype is not None:
            msg['exception'] = traceback.format_exception_only(etype, einst)[0].rstrip()
            msg['traceback'] = ''.join(traceback.format_tb(exc_tb)).splitlines()

        self._last.append((rec, msg))

        return json.dumps(msg, indent=True, default=self.json_serialize_dates)


class RotatingJSONFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, path, *args, **kws):
        path = Path(path)
        if path.exists() and path.stat().st_size > 2:
            self.empty = False
        else:
            self.empty = True

        self.terminator = ''
        self.cached_recs = []

        super().__init__(path, *args, **kws)

    def emit(self, rec):
        self.cached_recs.append(rec)

    def close(self):
        if len(self.cached_recs) == 0:
            super().close()
            return

        self.stream.write('[\n')
        if not self.empty:
            self.stream.write(',\n')

        for rec in self.cached_recs:
            super().emit(rec)
            if rec is not self.cached_recs[-1]:
                self.stream.write(',\n')
        self.stream.write('\n]')
        super().close()


class Host(core.Device):
    time_format = '%Y-%m-%d %H:%M:%S'

    def open(self):
        log_formatter = JSONFormatter()
        stream = LogStreamBuffer()
        sh = logging.StreamHandler(stream)
        sh.setFormatter(log_formatter)
        sh.setLevel(logging.DEBUG)

        # Add to the labbench logger handler
        logger = logging.getLogger('labbench')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(sh)

        # git repository information
        try:
            repo = find_repo_in_parents('.')
            self._logger.debug(f'running in git repository at {repo.path}')
        except repo.NotGitRepository:
            repo = None
            self._logger.info('not running in a git repository')

        self.backend = {
            'logger': logger,
            'log_stream': stream,
            'log_handler': sh,
            'log_formatter': log_formatter,
            'repo': repo,
        }

        # Preload the git repo parameters
        for name in attr.get_class_attrs(self).keys():
            if name.startswith('git'):
                getattr(self, name)

    def close(self):
        try:
            self.backend['logger'].removeHandler(self.backend['log_handler'])
        except (AttributeError, TypeError):
            pass
        try:
            self.backend['log_stream'].close()
        except (AttributeError, TypeError):
            pass

    def metadata(self):
        """Generate the metadata associated with the host and python distribution"""
        return dict(python_modules=self.__python_module_versions())

    def __python_module_versions(self):
        """Enumerate the versions of installed python modules"""

        versions = dict(
            [str(d).lower().split(' ') for d in pip.get_installed_distributions()]
        )
        running = dict(
            sorted(
                [(k, versions[k.lower()]) for k in sys.modules.keys() if k in versions]
            )
        )
        return pd.Series(running).sort_index()

    @attr.property.str()
    def time(self):
        """Get a timestamp of the current time"""
        now = datetime.datetime.now()
        return f'{now.strftime(self.time_format)}.{now.microsecond}'

    @attr.property.list()
    def log(self):
        """Get the current host log contents."""
        self.backend['log_handler'].flush()
        txt = self.backend['log_stream'].read()
        if len(txt) > 1:
            self._txt = txt
            self._serialized = '[' + txt[:-2] + ']'
            self._ret = json.loads(
                self._serialized
            )  # self.backend['log_stream'].read().replace('\n', '\r\n')
            return self._ret
        else:
            return {}

    @attr.property.str(cache=True, allow_none=True)
    def git_commit_id(self):
        """the unique identifier hash that can be used to access the current commit in the git repo"""
        repo = self.backend['repo']
        if repo is None:
            return None
        else:
            return repo.head().decode()

    @attr.property.str(cache=True, allow_none=True)
    def git_remote_url(self):
        """the remote URL of the repository of the current git repo"""
        repo = self.backend['repo']
        if repo is None:
            return None
        else:
            return repo.get_config().get(('remote', 'origin'), 'url').decode()

    @attr.property.str(cache=True)
    def hostname(self):
        """Get the name of the current host"""
        return socket.gethostname()

    @attr.property.str(cache=True)
    def git_browse_url(self):
        """URL for browsing the current git repository"""
        return f'{self.git_remote_url}/tree/{self.git_commit_id}'

    @attr.property.list(cache=True)
    def git_pending_changes(self):
        """unstaged changes to files in the repository"""
        repo = self.backend['repo']
        if repo is None:
            return []
        else:
            names = porcelain.status(repo, untracked_files='no').unstaged
            return [n.decode() for n in names]
