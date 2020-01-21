# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

import time
t0 = time.time()

from . import core
import datetime
import os
import socket
import logging
import sys
import io
import pandas as pd

__all__ = ['Host', 'Email', 'LogStderr']


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
    ''' This "Device" logs a copy of messages on sys.stderr while connected.
    '''
    log = ''

    def connect(self):
        self._stderr, self._buf, sys.stderr = sys.stderr, io.StringIO(), self

    def disconnect(self):
        if self.connected:
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
    ''' Sends a notification message on disconnection. If an exception
        was thrown, this is a failure subject line with traceback information
        in the main body. Otherwise, the message is a success message in the
        subject line. Stderr is also sent.
    '''

    resource: core.Address\
        (default='smtp.nist.gov', help='smtp server to use')

    port: core.Int\
        (default=25, min=1, help='TCP/IP port')
    
    sender: core.Unicode\
        (default='myemail@nist.gov', help='email address of the sender')
    
    recipients: core.List\
        (default=['myemail@nist.gov'], help='list of email addresses of recipients')

    success_message: core.Unicode\
        (default='Test finished normally', help='subject line for test success emails (None to suppress the emails)')

    failure_message: core.Unicode\
        (default='Exception ended test early', help='subject line for test failure emails (None to suppress the emails)')

    def _send(self, subject, body):
        sys.stderr.flush()
        self.backend.flush()
        from email.mime.text import MIMEText
        import smtplib

        msg = MIMEText(body, 'html')
        msg['From'] = self.settings.sender
        msg['Subject'] = subject
        msg['To'] = ", ".join(self.settings.recipients)
        self.server = smtplib.SMTP(self.settings.resource, self.settings.port)
        
        try:
            self.server.sendmail(self.settings.sender,
                                 self.settings.recipients,
                                 msg.as_string())
        finally:
            self.server.quit()

    def connect(self):
        self.backend = LogStderr()
        self.backend.connect()

    def disconnect(self):
        if self.connected:
            self.backend.disconnect()
            time.sleep(1)
            self.send_summary()

    def send_summary(self):
        ''' Sends the summary email containing the final state of the test.
        '''
        from traceback import format_exc

        exc = sys.exc_info()

        if exc[0] is KeyboardInterrupt:
            return

        if exc != (None, None, None):
            if self.settings.failure_message is None:
                return
            subject = self.settings.failure_message
            message = '<b>Exception</b>\n'\
                      + '<font face="Courier New, Courier, monospace">'\
                      + format_exc()\
                      + '</font>'
        else:
            if self.settings.success_message is None:
                return
            subject = self.settings.success_message
            message = ''

        if len(self.backend.log) > 0:
            message = message \
                + '\n\n<b>Standard error</b>\n'\
                + '<font face="Courier New, Courier, monospace">'\
                + self.backend.log\
                + '</font>'

        self._send(subject, message.replace('\n', '<br>'))

        return subject, message


class Host(core.Device):
    log_format = '%(asctime)s.%(msecs).03d %(levelname)10s %(message)s'
    time_format = '%Y-%m-%d %H:%M:%S'

    def connect(self):
        ''' The host setup method tries to commit current changes to the tree
        '''
        logger = logging.getLogger('labbench')
        logger.setLevel(logging.DEBUG)
        stream = LogStreamBuffer()
        sh = logging.StreamHandler(stream)
        sh.setFormatter(logging.Formatter(self.log_format, self.time_format))
        sh.setLevel(logging.DEBUG)
        logger.addHandler(sh)
        self.backend = {'logger': logger,
                        'log_stream': stream,
                        'log_handler': sh}

        try:
            self.repo = git.Repo('.', search_parent_directories=True)
        except git.NoSuchPathError:
            self.repo = None
            self.backend['logger'].warning(
                f"no git commit because {os.path.abspath('.')} is not in a repository")
        else:
            self.repo.index.commit('start of measurement')

    @classmethod
    def __imports__(self):
        global git, pip
        import git
        import pip

    def disconnect(self):
        try:
            self.backend['logger'].removeHandler(self.backend['log_handler'])
        except (AttributeError, TypeError):
            pass
        try:
            self.backend['log_stream'].close()
        except (AttributeError, TypeError):
            pass

    def metadata(self):
        ''' Generate the metadata associated with the host and python distribution
        '''
        ret = super().metadata()
        ret['python_modules'] = self.__python_module_versions()
        return ret

    def __python_module_versions(self):
        ''' Enumerate the versions of installed python modules
        '''
        versions = dict([str(d).lower().split(' ')
                         for d in pip.get_installed_distributions()])
        running = dict(sorted([(k, versions[k.lower()])
                               for k in sys.modules.keys() if k in versions]))
        return pd.Series(running).sort_index()
   
    @core.Unicode()
    def time(self):
        ''' Get a timestamp of the current time
        '''
        now = datetime.datetime.now()
        return f'{now.strftime(self.time_format)}.{now.microsecond}'

    @core.Unicode()
    def log(self):
        ''' Get the current host log contents.
        '''
        self.backend['log_handler'].flush()
        return self.backend['log_stream'].read().replace('\n', '\r\n')
    
    @core.Unicode(cache=True)
    def git_commit_id(self):
        ''' Try to determine the current commit hash of the current git repo
        '''
        try:
            commit = self.repo.commit()
            return commit.hexsha
        except git.NoSuchPathError:
            return ''

    @core.Unicode(cache=True)
    def git_remote_url(self):
        ''' Try to identify the remote URL of the repository of the current git repo
        '''
        try:
            return next(self.repo.remote().urls)
        except BaseException:
            return ''

    @core.Unicode(cache=True)
    def hostname(self):
        ''' Get the name of the current host
        '''
        return socket.gethostname()

    @core.Unicode(cache=True)
    def git_browse_url(self):
        ''' URL for browsing the current git repository
        '''
        return '{}/tree/{}'.\
               format(self.git_remote_url, self.git_commit_id)

if __name__ == '__main__':
    #    core.show_messages('DEBUG')
    #
    #    with Host() as pc:
    #        print(pc.time)

    with Email(recipients=['daniel.kuester@nist.gov']) as email:
        pass
