# Mail fetch and forward script
# Fetches mail from a target POP3 server, removes all X header extensions, rewrites the target address and forwards the mail to a list of recipients
# Schier Michael

import poplib
import smtplib
import email
import email.header
from datetime import datetime
import fcntl

maildir = "/opt/simple_list_mailer/mail/"
mailRecipientsFile = "/opt/simple_list_mailer/recipients.txt"
mailBannedFile = "/opt/simple_list_mailer/banned.txt"

subjectPrefix = "[ML] "
listAddr = "mailing-list@email.com"
pophost = "pop.email.com"
smtphost = "smtp.email.com"
popuser = "mailing-list_pop"
smtpuser = "mailing-list_smtp"
poppass = "mailing-list_pop_pass"
smtppass = "mailing-list_smtp_pass"

def getRecipients():
	recipients = []
	f = open(mailRecipientsFile, "r")
	for line in f:
		recipients.append(line.strip())
	f.close()
	return recipients

def getBanned():
	banned = []
	f = open(mailBannedFile, "r")
	for line in f:
		banned.append(line.strip())
	f.close()
	return banned

def setRecipients(recipients):
	f = open(mailRecipientsFile, "w")
	for r in recipients:
		f.write(r + "\n")
	f.close()

def plainMail(mailaddr):
	while mailaddr.count("<")>0:
		mailaddr = mailaddr[mailaddr.index("<")+1:]
	while mailaddr.count(">")>0:
		mailaddr = mailaddr[:mailaddr.index(">")]
	return mailaddr.lower()

def forwardMsg(smtpcon, msg):
	allowed = ['From', 'Date', 'Subject', 'Message-ID', 'MIME-Version', 'Content-Type', 'Content-Transfer-Encoding', 'In-Reply-To', 'References', 'Received']
	for item in msg.items():
		if allowed.count(item[0]) == 0:
#			print "Removing " + item[0] + ": " + item[1]
			del msg[item[0]]
	msg['Reply-To'] = listAddr
	msg['To'] = listAddr
	subject = msg['Subject']
	if subject == None:
		subject = ""
	subjectheader = email.header.decode_header(subject)[0]
	subject = subjectheader[0]
	charset = subjectheader[1]
	for bad in [subjectPrefix, "Antwort: ", "RE: ", "Re: ", "AW: ", "Aw: "]:
		subject = subject.replace(bad, "") 
	subject = subjectPrefix + subject
	del msg['Subject']
	msg['Subject'] = subject
	subject = email.header.make_header([(subject,charset)]).encode()
	
	# avoid bouncing
	msgfrom = plainMail(msg['from'])
	for toEmail in getRecipients():
		if toEmail == msgfrom:
			print "SKIP " + toEmail
			continue
		print "RELAY " + toEmail
		smtpcon.sendmail(listAddr, toEmail, msg.as_string())

def logMsg(msg):
	f = open(maildir + datetime.today().strftime("%Y-%m-%d %H:%M:%S") + " " + plainMail(msg['From']) + ".txt", "w")
	f.write(msg.as_string())
	f.close()

def adminMsg(smtpcon, msg):
	print "ADMIN " + msg['Subject']
	cmd = msg['Subject'][6:]
	newmsg = email.message.Message()
	newmsg['From'] = listAddr;
	newmsg['To'] = plainMail(msg['From'])
	newmsg['Subject'] = "admin-response to " + cmd

	body = ""
	recipients = getRecipients()
	if cmd[:5] == "query":
		body = "Recipients of mailing-list " + listAddr + ":\r\n\r\n"
		for r in recipients:
			body += r + "\r\n"
	elif cmd[:3] == "del":
		for m in cmd[3:].split():
			m = m.lower()
			m = m.replace("<","").replace(">","")
			if recipients.count(m) == 0:
				body += "Recipient " + m + " not in list\r\n"
				continue
			recipients.remove(m)
			body += "Removed recipient " + m + "\r\n"
		setRecipients(recipients)
	elif cmd[:3] == "add":
		for m in cmd[3:].split():
			m = m.lower()
			m = m.replace("<","").replace(">","")
			if recipients.count(m) > 0:
				body += "Recipient " + m + " already in list\r\n"
				continue
			recipients.append(m)
			body += "Added recipient " + m + "\r\n"
		setRecipients(recipients)
	else:
		body += "Admin commands to be placed in the subject line:\r\n"
		body += "admin query\r\n"
		body += "admin add <addr1> <addr2> ... <addrn>\r\n"
		body += "admin del <addr1> <addr2> ... <addrn>\r\n"
	newmsg.set_payload(body)
	smtpcon.sendmail(listAddr, newmsg['To'], newmsg.as_string())

def main():
	try:
		#conn = poplib.POP3(pophost)
		popcon = poplib.POP3_SSL(pophost)
		popcon.user(popuser)
		popcon.pass_(poppass)
	except poplib.error_proto:
		print "POP3 connection error"
		return
	
	msglist = popcon.list()[1]
	pending = []
	for i in msglist:
		msgnum = i.split(" ")[0]
		msg = popcon.retr(msgnum)
		msg = msg[1]
		msg = "\r\n".join(msg)
		msg = email.message_from_string(msg)
		if not msg.has_key('Subject'):
			msg['Subject'] = ""
		isSpam = False
		for banned in getBanned():
			if plainMail(msg['From']) == banned:
				isSpam = True
		if isSpam:
			print "SPAM " + plainMail(msg['From']) + "\n"
			popcon.dele(msgnum)
			continue
		logMsg(msg)
		pending.append([msgnum,msg])
	
	if len(pending) == 0:
		popcon.quit()
		return

	smtpcon = smtplib.SMTP(smtphost)
	smtpcon.starttls()
	#smtpcon = smtplib.SMTP_SSL(smtphost)
	#smtpcon.set_debuglevel(1)
	smtpcon.login(smtpuser, smtppass)

	for [num,msg] in pending:
		print "FROM " + plainMail(msg['From'])
		if msg['Subject'][0:5] == "admin":
			adminMsg(smtpcon, msg)
		else:
			print "SUBJECT " + msg['Subject']
			forwardMsg(smtpcon, msg)
		popcon.dele(num)
		print ""

	popcon.quit()
	smtpcon.quit()

#----------------------------------------------

if __name__ == "__main__":
	lockfile = open('/tmp/simple_list_mailer.lock', 'w')
	try:
		fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
	except IOError:
		print "The script is already running"
		quit()

	try:
		main()
	finally:
		fcntl.flock(lockfile, fcntl.LOCK_UN | fcntl.LOCK_NB)
