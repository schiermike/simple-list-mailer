Simple List Mailer
==================

This python daemon can be used to quickly setup a mailing list using an external POP account such as gmx or gmail.

It acts as a daemon and can be installed with init, supervise, or whatever your favourite daemon management tool might be.

*Simple List Mailer* periodically checks for new mail in a given account, rewrites the header information and sends the mail to a set of recipients.

Participants can be added and removed via admin commands in the subject line of a mail.
In the same way, *Simple List Mailer* allows blocking of mail addresses.

Installation
------------

1. Check that you have python installed as well as python's ``smtplib``, ``poplib``, and ``imaplib``

2. Adjust the config.cfg file (set credentials, check interval, recipients, etc)

3. If you don't want to start the process directly but want to use e.g. supervise to run the daemon instead, add the
   run configuration to the /etc/service folder.

Notes
-----

The current implementation sends an email to each registered address in a loop. When there is a high number of
subscribers, this is clearly not an optimal solution especially in the presence of large attachments. Using the
BCC field for all receivers is a good alternative!