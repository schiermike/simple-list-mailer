"""
Mail fetch and forward script

Fetches mail from a target POP3 server, removes all X header extensions, rewrites the target address and forwards 
the mail to a list of recipients
"""

import os
import time
import poplib
import smtplib
import email
import sys
import ConfigParser
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
log = logging.getLogger()


def clean_mail_address(addr):
    while addr.count('<') > 0:
        addr = addr[addr.index('<') + 1:]
    while addr.count('>') > 0:
        addr = addr[:addr.index('>')]
    return addr.lower()


class SimpleListMailer(object):

    def __init__(self, config_filename):
        self.__config_filename = config_filename

    @property
    def list_address(self):
        return clean_mail_address(self.config.get('DEFAULT', 'address'))

    @property
    def config(self):
        config = ConfigParser.RawConfigParser()
        config.read(self.__config_filename)
        return config

    @property
    def recipients(self):
        s = self.config.get('DEFAULT', 'recipients')
        return map(str.lower, map(str.strip, s.split()))

    @recipients.setter
    def recipients(self, value):
        c = self.config
        value.sort()
        value = ' '.join(value)
        c.set('DEFAULT', 'recipients', value)
        with open(self.__config_filename, 'wb') as configfile:
            c.write(configfile)

    @property
    def banned(self):
        s = self.config.get('DEFAULT', 'banned')
        return map(str.lower, map(str.strip, s.split()))

    @banned.setter
    def banned(self, value):
        c = self.config
        value.sort()
        value = ' '.join(value)
        c.set('DEFAULT', 'banned', value)
        with open(self.__config_filename, 'wb') as configfile:
            c.write(configfile)

    @property
    def subject_prefix(self):
        return self.config.get('DEFAULT', 'subject_prefix')

    @property
    def stripped_subject_prefixes(self):
        s = self.config.get('DEFAULT', 'stripped_subject_prefixes')
        return map(str.strip, s.split())

    def _handle_admin_msg(self, pop_connection, smtp_connection, msg):
        subject = msg['Subject']
        log.info('Admin message received: <%s>' % subject)

        cmd = subject[6:]
        newmsg = email.message.Message()
        newmsg['From'] = self.list_address
        newmsg['To'] = clean_mail_address(msg['From'])
        newmsg['Subject'] = 'admin-response to %s' % cmd

        cmd = cmd.split()
        args = cmd[1:]
        cmd = cmd[0] if cmd else ''
        body = ''
        recipients = self.recipients
        banned = self.banned
        if cmd == 'del':
            for recipient in args:
                recipient = clean_mail_address(recipient)
                if recipient not in recipients:
                    log.info('Unable to remove recipient <%s>' % recipient)
                    body += 'Unable to remove recipient <%s>\r\n' % recipient
                else:
                    recipients.remove(recipient)
                    log.info('Removed recipient <%s>' % recipient)
                    body += 'Removed recipient <%s>\r\n' % recipient
            self.recipients = recipients
        elif cmd == 'add':
            for recipient in args:
                recipient = clean_mail_address(recipient)
                if recipient in recipients:
                    log.info('Recipient <%s> is already member of this list' % recipient)
                    body += 'Recipient <%s> is already member of this list\r\n' % recipient
                else:
                    recipients.append(recipient)
                    log.info('Added recipient <%s>' % recipient)
                    body += 'Added recipient <%s>\r\n' % recipient
            self.recipients = recipients
        elif cmd == 'unban':
            for recipient in args:
                recipient = clean_mail_address(recipient)
                if recipient not in banned:
                    log.info('Unable to unban sender <%s>' % recipient)
                    body += 'Unable to unban sender <%s>\r\n' % recipient
                else:
                    banned.remove(recipient)
                    log.info('Unbanned sender <%s>' % recipient)
                    body += 'Unbanned sender <%s>\r\n' % recipient
            self.banned = banned
        elif cmd == 'ban':
            for recipient in args:
                recipient = clean_mail_address(recipient)
                if recipient in banned:
                    log.info('Sender <%s> has already been banned' % recipient)
                    body += 'Sender <%s> has already been banned\r\n' % recipient
                else:
                    banned.append(recipient)
                    log.info('Banned sender <%s>' % recipient)
                    body += 'Banned sender <%s>\r\n' % recipient
            self.banned = banned
        else:
            body += 'Ignoring unknown admin command <%s>\r\n\r\n' % subject
            body += 'Admin commands to be placed in the subject line:\r\n'
            body += 'admin add <addr1> <addr2> ... <addrn>\r\n'
            body += 'admin del <addr1> <addr2> ... <addrn>\r\n'
            body += 'admin ban <addr1> <addr2> ... <addrn>\r\n'
            body += 'admin unban <addr1> <addr2> ... <addrn>\r\n'

        body += '\r\n\r\n***** Recipients of mailing-list %s *****\r\n' % self.list_address
        for recipient in self.recipients:
            body += '  %s\r\n' % recipient

        body += '\r\n\r\n***** Banned from mailing-list %s *****\r\n' % self.list_address
        for banned in self.banned:
            body += '  %s\r\n' % banned

        newmsg.set_payload(body)
        smtp_connection.sendmail(self.list_address, newmsg['To'], newmsg.as_string())

        pop_connection.dele(msg.num)
        log.info('Deleted admin mail <%s>' % msg.num)

    def _forward_mail(self, pop_connection, smtp_connection, msg):
        allowed_headers = ['From', 'Date', 'Subject', 'Message-ID', 'MIME-Version', 'Content-Type',
                           'Content-Transfer-Encoding', 'In-Reply-To', 'References', 'Received']
        for item in msg.items():
            if item[0] not in allowed_headers:
                del msg[item[0]]

        msg['Reply-To'] = self.list_address
        msg['To'] = self.list_address
        subject = msg['Subject']
        if not subject:
            subject = ''
        subject_header = email.header.decode_header(subject)[0]
        subject, charset = subject_header[0:2]

        for bad in [self.subject_prefix] + self.stripped_subject_prefixes:
            subject = subject.replace(bad, '')
        subject = self.subject_prefix + subject
        subject = subject.strip()
        del msg['Subject']
        msg['Subject'] = email.header.make_header([(subject, charset)]).encode()

        # avoid bouncing
        from_addr = clean_mail_address(msg['from'])
        to_addrs = filter(lambda r: self.config.getboolean('DEFAULT', 'bounce') or from_addr != r, self.recipients)
        log.info('Forwarding to <%s>, subject: <%s>' % (to_addrs, subject))
        smtp_connection.sendmail(self.list_address, to_addrs, msg.as_string())

        pop_connection.dele(msg.num)
        log.info('Deleted mail <%s>' % msg.num)

    def _archive_message(self, msg):
        archive_dir = self.config.get('DEFAULT', 'archive_dir')
        sender_address = clean_mail_address(msg['From'])
        file_name = '%s %s.txt' % (datetime.today().strftime('%Y-%m-%d %H:%M:%S'), sender_address)

        with open(os.path.join(archive_dir, file_name), 'w') as archive_file:
            archive_file.write(msg.as_string())

    def deliver(self):
        try:
            pop_connection = poplib.POP3_SSL(self.config.get('POP', 'host'))
            pop_connection.user(self.config.get('POP', 'user'))
            pop_connection.pass_(self.config.get('POP', 'password'))
        except poplib.error_proto, e:
            log.error('POP3 connection error: %s' % e)
            return

        messages = pop_connection.list()[1]
        pending = []
        for msg_line in messages:
            msg_num = msg_line.split(' ')[0]
            log.info('Fetching mail <%s>' % msg_num)
            msg = pop_connection.retr(msg_num)
            msg = msg[1]
            msg = '\r\n'.join(msg)
            msg = email.message_from_string(msg)
            if 'Subject' not in msg:
                msg['Subject'] = ''

            # check whether email address is on blacklist
            is_spam = False
            sender_address = clean_mail_address(msg['From'])
            for banned_address in self.banned:
                is_spam |= (sender_address == banned_address)
            if is_spam:
                log.info('Ignoring spam from <%s>' % sender_address)
                pop_connection.dele(msg_num)
                continue

            msg.num = msg_num
            msg.sender_address = sender_address
            self._archive_message(msg)
            pending.append(msg)

        if len(pending) == 0:
            pop_connection.quit()
            return

        if self.config.getboolean('SMTP', 'use_tls'):
            smtp_connection = smtplib.SMTP(self.config.get('SMTP', 'host'))
            smtp_connection.starttls()
        else:
            smtp_connection = smtplib.SMTP_SSL(self.config.get('SMTP', 'host'))

        smtp_connection.login(self.config.get('SMTP', 'user'), self.config.get('SMTP', 'password'))

        for msg in pending:
            log.info('Processing mail <%s> from <%s>' % (msg.num, msg.sender_address))
            if msg['Subject'][0:5] == 'admin':
                self._handle_admin_msg(pop_connection, smtp_connection, msg)
            else:
                self._forward_mail(pop_connection, smtp_connection, msg)

        pop_connection.quit()
        smtp_connection.quit()

    def loop(self):
        while True:
            self.deliver()
            time.sleep(self.config.getint('DEFAULT', 'interval'))


def main():
    config_filename = sys.argv[1] if len(sys.argv) == 2 else 'config.cfg'
    mailer = SimpleListMailer(config_filename)

    log.setLevel(logging.INFO)
    log_file = os.path.join(mailer.config.get('DEFAULT', 'log_dir'), 'simple_list_mailer.log')
    handler = TimedRotatingFileHandler(log_file, when='W0')
    handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s'))
    log.addHandler(handler)

    log.info(' Simple List Mailer '.center(80, '='))
    mailer.loop()


if __name__ == '__main__':
    main()