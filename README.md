Simple List Mailer
==================

This python script can be used to quickly setup a mailing list using an external POP account such as gmx or gmail.

When installed e.g. as cronjob, *Simple List Mailer* periodically checks for new mail in a given account, rewrites the header information and sends the mail to a set of recipients.

Participants can be added and removed via admin commands in the subject line of a mail. In the same way, *Simple List Mailer* allows blocking of mail addresses.

Installation
------------

1. Check that you have python installed as well as python's ``smtplib``, ``poplib``, and ``imaplib``

2. Adjust the path settings:

        maildir = "/opt/simple_list_mailer/mail/"
        maildir = "/opt/simple_list_mailer/mail/"
        mailRecipientsFile = "/opt/simple_list_mailer/recipients.txt"
        mailBannedFile = "/opt/simple_list_mailer/banned.txt"

3. Adjust the mailing list properties:

        subjectPrefix = "[ML] "
        listAddr = "mailing-list@email.com"

4. Set the credentials for the incoming and the outgoing servers.

        pophost = "pop.email.com"
        smtphost = "smtp.email.com"
        popuser = "mailing-list_pop"
        smtpuser = "mailing-list_smtp"
        poppass = "mailing-list_pop_pass"
        smtppass = "mailing-list_smtp_pass"

Notes
-----

The current implementation sends an email to each registered address in a loop. When there is a high number of subscribers, this is clearly not an optimal solution especially in the presence of large attachments. Using the BCC field for all receivers is a good alternative!