from PyEmailHandler import EmailSMTP, EmailIMAP
from PyEmailHandler.tools import reply_mail
from PyEmailHandler.mailer import cast
from email.mime.text import MIMEText
from email.utils import parseaddr
import email
import time
import traceback
import sys
import configparser
__version__ = "v1.6"
config_name = 'config.ini'

config = configparser.ConfigParser()
config.read(config_name, encoding='UTF-8')
#Credentials
config_Creds = config['Credentials']
smtp_username = config_Creds['mail.smtp.username']
smtp_password = config_Creds['mail.smtp.password']
imap_username = config_Creds['mail.imap.username']
imap_password = config_Creds['mail.imap.password']
#Content
config_Content = config['Content']
SENDER_FROM = config_Content['mail.sendermail']
REPLY_TO = config_Content['mail.replymail']
SENDER_NAME = config_Content['mail.sendername']
#configuration
config_Mailserver = config['Mailserver']
SMTPServ = config_Mailserver['mail.smtp.server']
SMTPport = config_Mailserver['mail.smtp.port']
SMTPconn = config_Mailserver['mail.smtp.sslmode']
IMAPServ = config_Mailserver['mail.imap.server']
IMAPport = config_Mailserver['mail.imap.port']
IMAPconn = config_Mailserver['mail.imap.sslmode']
#Email
html = open(config_Content['mail.body'],'r').read()
from loguru import logger
logger.remove()
logging = logger.bind(name="GoReply")
logging.add(sys.stdout, colorize=True, format="<green>[GoReply]</green><yellow>{time}</yellow><level>[{level}]{message}</level>")
refresh = 15
#LDB
recent = []

def email_exist(email):
    current_time = time.time()
    for entry in recent:
        if entry['email_address'] == email:
            status = current_time < entry['time']
            if not status: recent.remove(entry)
            return status
    return False

def time_elapsed_since_epoch(timestamp):
    current_time = time.time()
    elapsed_time = current_time - timestamp
    return elapsed_time

def add_email(email):
    cooldown = 86400  # 1 day cooldown
    current_time = time.time()
    recent.append({'email_address': email, 'time': current_time + cooldown})

def check_mail(address):
    return email_exist(address)

def process_mail(mail):
    sendto = mail['Reply-To'] or mail['From']
    receiver_name, receiver_address = parseaddr(sendto)
    try:
        logging.info(f'Detected new mail from: {mail["From"]}({mail["Reply-To"] if mail["Reply-To"] else ""}), sending autoreply...')
        #This part is important to stop spammy autoresponse
        if check_mail(receiver_address):
            logging.info(f'Mail address under cooldown, deleting mail')
            imap.delete_mail(mail)
            logging.info('Deleted mail')
            return
        else:
            add_email(receiver_address)
        message = MIMEText(html, 'html')
        message['Reply-To'] = REPLY_TO
        reply_mail(smtp, mail, message=message)
        logging.info('Reply sent, deleting mail...')
        imap.delete_mail(mail)
        logging.info('Deleted mail')
    except Exception as e:
        logging.exception("Unexpected error while processing email: " + str(e) + ".")

def login_to_mail():
    imap = EmailIMAP(
        username=imap_username,
        password=imap_password,
        imap_server=IMAPServ,
        port=IMAPport,
        protocol=IMAPconn      
    )
    imap.start_connection()
    logging.info('IMAP Connection Established')
    smtp = EmailSMTP(
        username=smtp_username,
        password=smtp_password,
        sender_mail=SENDER_FROM,
        sender_name=SENDER_NAME,
        smtp_server=SMTPServ,
        port = SMTPport,
        protocol = SMTPconn
    )
    smtp.start_connection()
    logging.info('SMTP Connection Established')
    logging.info('Checking folders')
    pre_start(imap)
    logging.info('GoReply Successfully initialized')
    logging.info('Refresh Time: %s' % refresh)
    return imap, smtp

def main():
    global imap, smtp
    logging.info(f'====GoReply {__version__}====')
    imap, smtp = login_to_mail()
    while True:
        try:
            mails = imap.get_mails()
            for mail in mails:
                process_mail(mail)
            time.sleep(refresh)
        except TimeoutError as e:
            print("Timeout error detected, refreshing login")
            imap, smtp = login_to_mail()

def pre_start(imap):
    if not imap.get_folder('Trash'):
        if imap.create_folder('Trash'):
            logging.info('Folder Trash Created successfully')
        else:
            logging.error('Folder Trash cannot be created')
            sys.exit(1)
    if not imap.get_folder('Inbox'):
        if imap.create_folder('Inbox'):
            logging.info('Folder Inbox Created successfully')
        else:
            logging.error('Folder Inbox cannot be created')
            sys.exit(1)

if __name__ == '__main__':
    main()