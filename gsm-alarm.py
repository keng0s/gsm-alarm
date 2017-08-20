#!/usr/bin/env python
from gsmmodem.exceptions import InterruptedException, CommandError
from gsmmodem.modem import GsmModem
import configparser
import platform
import logging
from time import sleep
import re
from db import DB
from datetime import datetime, date, timedelta


class GsmAlarm:
    def handle_sms(self, sms):
        print(
            u'== SMS message received ==\nFrom: {0}\nTime: {1}\nMessage:\n{2}\n'.format(
                sms.number, sms.time, sms.text
            )
        )
        regex = r"([0-9]{1,2}:(?:[0-9]{2})?)"

        matches = re.finditer(regex, sms.text, re.IGNORECASE)
        for match in matches:
            try:
                time_str = str(match.group())
                scheduled_time = datetime.combine(date.today(), datetime.strptime(time_str, '%H:%M').time())
                if scheduled_time <= datetime.now():
                    scheduled_time += timedelta(days=1)
                self.db.query('insert into messages(number, sent, received, scheduled) values (%s, %s, %s, %s)',
                              (sms.number, sms.time, datetime.now().isoformat(), scheduled_time))
                sms.reply(u'OK: ' + time_str)
            except ValueError:
                print('Unknown time: ' + time_str)
                sms.reply(u'Unknown time: ' + time_str)

    def read_messages(self):
        messages = self.db.fetchall('select * from messages where called is null', ())
        for message in messages:
            msg_id = message[0]
            scheduled_time = message[4]
            number = message[1]
            if scheduled_time is not None:
                if scheduled_time <= datetime.now():
                    if number is not None:
                        result = self.call_out(number)
                    else:
                        result = -1

                    self.db.query('update messages set called = %s, result = %s where id = %s',
                                  (datetime.now().isoformat(), result, msg_id))

    def call_out(self, number):
        print('Dialing number: ' + number)
        try:
            call = self.modem.dial(number)
        except CommandError as e:
            print('Call failed: ' + str(e))
            return -1

        print('Waiting for call to be answered/rejected')
        answered = False
        while call.active:
            if call.answered:
                answered = True
                print('Call has been answered; waiting a while...')
                sleep(1.0)
                print('Playing DTMF tones...')
                try:
                    if call.active:
                        call.sendDtmfTone('111')
                except InterruptedException as e:
                    print('DTMF playback interrupted: {0} ({1} Error {2})'.format(e, e.cause.type, e.cause.code))
                except CommandError as e:
                    print('DTMF playback failed: {0}'.format(e))
                finally:
                    if call.active:
                        print('Hanging up call...')
                        call.hangup()
                    else:
                        print('Call has been ended by remote party')
            else:
                sleep(1.0)
        if not answered:
            print('Call was not answered by remote party')
        print('Done.')
        return int(answered)

    def listen(self):
        print('Waiting for SMS message...')
        try:
            while True:
                self.modem.processStoredSms(unreadOnly=True)
                self.read_messages()
                sleep(10)
        except KeyboardInterrupt:
            print('interrupted!')
            self.modem.close()

    def __init__(self):
        config = configparser.ConfigParser()
        if platform.system() == 'Windows':
            config.read('config/win/config.ini')
        elif platform.system() == 'Linux':
            config.read('config/nix/config.ini')
        else:
            raise Exception('Unknown system')

        port = config['modem']['PORT']
        baud_rate = int(config['modem']['BAUDRATE'])
        sim_pin = config['modem']['PIN']

        host = config['db']['host']
        username = config['db']['username']
        password = config['db']['password']
        db_name = config['db']['name']

        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

        print('Initializing modem...')
        self.modem = GsmModem(port, baud_rate, smsReceivedCallbackFunc=self.handle_sms)
        self.modem._smscNumber = '+3725099000'
        self.modem.connect(sim_pin)

        print('Connecting to the DB')
        self.db = DB(host, username, password, db_name)


if __name__ == '__main__':
    gsm_alarm = GsmAlarm()
    gsm_alarm.listen()
