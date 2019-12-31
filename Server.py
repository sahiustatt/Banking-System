import time
import ssl
import socket
import threading
import MySQLdb
import fpdf
from fpdf import FPDF
import smtplib
import calendar
from email.mime.text import MIMEText
import sys
import os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEBase import MIMEBase
from email import encoders

AUTHENTICATION_FAILURE = "authentication_failed"
AUTHENTICATION_SUCCESSFUL = "authentication_successfull"
SUCCESS = 0
ERROR = 1
LOGOUT = 2

class Response(object):
    def __init__(self):
        self.resType = ''
        self.resParams = {}

    def toString(self):
        s = "{}".format(self.resType)
        for k,v in self.resParams.items():
            s = "{}::{}:{}".format(s, k, v)
        #print"toString(): s =  " + s
        return s

class Request(object):
    def __init__(self, buf):
        print "\nNew Request ["+buf+"]"
        print "\n"
        values = buf.split('::')
        self.reqType = values[0]
        #print "Request Received ==> "+self.reqType
        self.reqParams = {}
        for elem in values[1:]:
            k, v = elem.split(':')
            self.reqParams[k] = v
            #print "\""+k+":"+v+"\" "

#########################  CLIENT THREAD CLASS #######################

class Client(threading.Thread):
    def __init__(self, ssock, addr):
        threading.Thread.__init__(self)
        self.sock = ssock
        self.addr = addr
        self.db = MySQLdb.connect(host="127.0.0.1", user="root", passwd="vaibhav", db="Bank")
        self.cursor = self.db.cursor()

    def run(self):
        print"waiting for login info from the client.."
        while True:
            #receive login request from the client
            try:
                data = self.sock.recv(1024)
                print data
            except:
                break
            result = self.process_request(data)
            if(result == ERROR):
                print "Error. Client connection closed."
                break
            elif(result == LOGOUT):
                print "Client done. Connection closed."
                break
        print "Closing the client connection"
        self.sock.close()
        self.db.close()
        return

    def send_error(self,msgtype,errmsg):
        #create response to send an error
        resp = Response()
        resp.resType = msgtype
        resp.resParams['status']='FAILED'
        resp.resParams['error']=errmsg
        self.sock.send(resp.toString())

    def process_request(self,buf):
        req = Request(buf)
        print"process_request(): reqType ==>"+req.reqType
        if req.reqType == 'LOGIN':
            return self.check_login(req)
        elif req.reqType == 'GET':
            self.service_get_request(req)    
        elif req.reqType == 'SET':
            self.service_set_request(req)
        elif req.reqType == 'INSERT':
            self.service_insert_request(req)
        elif req.reqType == 'DELETE':
            self.service_delete_request(req)
        else:
            #create response to send an error
            resp = Response()
            resp.resType = 'UNKNOWN_REQUEST'
            resp.resParams['status']='FAILED'
            resp.resParams['error']="invalid request type."
            self.sock.send(resp.toString())
            return ERROR

    def check_login(self, req):
        resp = Response()

        if "username" not in req.reqParams or \
            "password" not in req.reqParams or \
            req.reqParams["username"] == "" or \
            req.reqParams["password"] == "":
                self.send_error('LOGIN_RESPONSE','Invalid Username or password')
                return ERROR
        else: 
            
            sql = "SELECT * from customer_login WHERE USERNAME='{x}' AND PASSWORD=MD5('{y}')".format(x=req.reqParams["username"],y=req.reqParams["password"]) 
            print "sql query ==> " + sql
            try:
                self.cursor.execute(sql)
            except Exception as e:
                print e
                print "calling auth failure server side error"
                self.send_error('LOGIN_RESPONSE', 'Server side error')
                #self.sock.close()
                return ERROR
        
            print"db executed successfully"

            # fetch results (its a list)
            results = self.cursor.fetchone()
            if not results:
                print "calling auth failure user does not exist"
                self.send_error('LOGIN_RESPONSE','User does not exist')
                return  ERROR
            else:
                print"inside login else block"
                #print results[0]+","+results[1]+","+str(results[2])+","+results[3]
                resp.resType = 'LOGIN_RESPONSE'
                resp.resParams['status']='SUCCESS'
                resp.resParams['client_type']=results[3]
                resp.resParams['client_id']=str(results[2])
                print"before send"
                self.sock.send(resp.toString())
                print "after send"
                return SUCCESS

    def service_get_request(self, req):
        print"called service_get_request()\n"
        resp = Response()

        if req.reqParams['subreq_type'] == 'CUSTOMER_ID':
            self.get_customer_id(req)
        elif req.reqParams['subreq_type'] == 'CUSTOMER_ACCT':
            self.get_customer_acct(req)
        elif req.reqParams['subreq_type'] == 'CUSTOMER_TRANSACTION':
            self.get_customer_transactions(req)
        elif req.reqParams['subreq_type'] == 'CUSTOMER_PROFILE':
            self.get_customer_profile(req)
        elif req.reqParams['subreq_type'] == 'ALL_TELLER_ID':
            self.get_teller_ids(req)
        elif req.reqParams['subreq_type'] == 'TELLER_PROFILE':
            self.get_teller_profile(req)
        elif req.reqParams['subreq_type'] == 'MONTH_TRANSACTIONS':
            self.get_month_transactions(req)
        elif req.reqParams['subreq_type'] == 'MONTHLY_STATEMENT':
            self.get_monthly_statement(req)
        else:
            self.send_error('GET_RESPONSE','Invalid Sub request sent.')
            return ERROR


    def service_set_request(self, req):
        print"service_set_request(): subreq_type ==>" + req.reqParams['subreq_type']
        if req.reqParams['subreq_type'] == 'UPDATE_CHK_ACCT':
            self.update_customer_acct(req)

        elif req.reqParams['subreq_type'] == 'UPDATE_SAV_ACCT':
            self.update_customer_acct(req)

        elif req.reqParams['subreq_type'] == 'UPDATE_CUSTOMER_PROFILE':
            self.update_customer_profile(req)

        elif req.reqParams['subreq_type'] == 'UPDATE_TELLER_PROFILE':
            self.update_teller_profile(req)

        elif req.reqParams['subreq_type'] == 'TRANSFER_MONEY':
            self.transfer_money(req)

        else:
            self.send_error('GET_RESPONSE','Invalid Sub request sent.')
            return ERROR

    def service_insert_request(self, req):
        print"called service_insert_request()"
        if req.reqParams['subreq_type'] == 'INSERT_LOGIN_RECORD':
            self.insert_login_record(req)
        elif req.reqParams['subreq_type'] == 'INSERT_ACCT_RECORD':
            self.insert_accounts_record(req)
        elif req.reqParams['subreq_type'] == 'INSERT_PROFILE_RECORD':
            self.insert_profile_record(req)
        else:
            self.send_error('INSERT_RESPONSE','Invalid Subreq_type sent.')
            return ERROR


    def service_delete_request(self, req):
        print "service_delete_request()"
        if req.reqParams['subreq_type'] == 'DELETE_LOGIN_RECORD':
            self.delete_login_record(req)
        elif req.reqParams['subreq_type'] == 'DELETE_ACCT_RECORD':
            self.delete_accounts_record(req)
        elif req.reqParams['subreq_type'] == 'DELETE_PROFILE_RECORD':
            self.delete_profile_record(req)
        else:
            self.send_error('DELETE_RESPONSE','Invalid Subreq_type sent.')
            return ERROR

    ###########################  GET FUNCTIONS  ############################

    def get_customer_profile(self, req):
        print "called get_customer_profile()"
        if "customer_id" not in req.reqParams or \
                req.reqParams["customer_id"] == "" :
            self.send_error('GET_RESPONSE','Invalid Customer ID')
            return ERROR
        else: 
            resp = Response()
            sql = "SELECT * from CUSTOMER_INFO_TABLE WHERE CUSTOMER_ID='{x}'".format(x=req.reqParams["customer_id"]) 
            #print "sql query ==> " + sql
            try:
                self.cursor.execute(sql)
            except Exception as e:
                print e
                self.send_error('GET_RESPONSE', 'Server error: DB operation failed.')
                return ERROR

            # fetch results (its a list)
            results = self.cursor.fetchone()
            if not results:
                #print "get_customer_profile():Request failure-Record does not exist"
                self.send_error('GET_RESPONSE','Record does not exist')
                return ERROR
            else:
                #print str(results[0])+","+results[1]+","+results[2]+","+results[3]+ \
                        #","+results[4]+","+results[5]+","+results[6]
                
                resp.resType = 'GET_RESPONSE'
                resp.resParams['status']='SUCCESS'
                resp.resParams['customer_id']=results[0]
                resp.resParams['first_name']=results[1]
                resp.resParams['last_name']=results[2]
                resp.resParams['DOB']=results[3]
                resp.resParams['email']=results[4]
                resp.resParams['phone']=results[5]
                resp.resParams['address']=str(results[6])+","+str(results[7])+","+str(results[8]) \
                        +","+str(results[9])+","+str(results[10])+","+str(results[11])
                self.sock.send(resp.toString())
                return SUCCESS


    def get_customer_id(self, req):
        print"called get_customer_id()"
        if "customer_name" not in req.reqParams or \
                req.reqParams["customer_name"] == "" :
            self.send_error('GET_RESPONSE','Invalid Username or password')
            return ERROR
        else: 
            resp = Response()
            sql = "SELECT * from customer_login WHERE USERNAME='{x}'".format\
                    (x=req.reqParams["customer_name"]) 
            #print "sql query ==> " + sql
            try:
                self.cursor.execute(sql)
            except Exception as e:
                print e
                #print " DB execute error"
                self.send_error('GET_RESPONSE', 'Server side error')
                return ERROR

            # fetch results (its a list)
            results = self.cursor.fetchone()
            if not results:
                print "get_customer_id:Request failure-Record does not exist"
                self.send_error('GET_RESPONSE','Record does not exist')
                return ERROR
            else:
                print "User_name: "+ req.reqParams['customer_name'] +","+"Id: "+ str(results[2])
                resp.resType = 'GET_RESPONSE'
                resp.resParams['status']='SUCCESS'
                resp.resParams['client_id']=results[2]
                self.sock.send(resp.toString())
                return SUCCESS

    def get_customer_chk_acct(self,customer_id):
        print"called get_customer_chk_acct()"
        sql = "SELECT * from ACCOUNT_TABLE WHERE CUSTOMER_ID='{x}'".format(x=customer_id) 
        #print "sql query ==> " + sql
        try:
            self.cursor.execute(sql)
        except Exception as e:
            print e
            return ERROR
            
        # fetch results (its a list)
        results = self.cursor.fetchone()
        if not results:
            return  ERROR
        else:
            return results[1], results[3]

    def get_customer_sav_acct(self,customer_id):
        print "called get_customer_sav_acct()"
        sql = "SELECT * from ACCOUNT_TABLE WHERE CUSTOMER_ID='{x}'".format(x=customer_id) 
        #print "sql query ==> " + sql
        try:
            self.cursor.execute(sql)
        except Exception as e:
            print e
            return ERROR
            
        # fetch results (its a list)
        results = self.cursor.fetchone()
        if not results:
            return  ERROR
        else:
            return results[2], results[4]


    def get_customer_acct(self, req):
        print"called get_customer_acct()"
        if "customer_id" not in req.reqParams or \
                req.reqParams["customer_id"] == "":
            self.send_error('GET_RESPONSE','Invalid key-value entries for customer_id')
            return ERROR
        else: 
            chk_acct_num, chk_acct_bal = self.get_customer_chk_acct(req.reqParams['customer_id'])
            sav_acct_num, sav_acct_bal = self.get_customer_sav_acct(req.reqParams['customer_id'])

            if chk_acct_num == '' or chk_acct_bal == '' or \
                    sav_acct_num == '' or sav_acct_num == '':
                #print "Failed to GET Records"
                self.send_error('GET_RESPONSE','Get operation failed')
                return  ERROR
            else:
                resp = Response()
                resp.resType = 'GET_RESPONSE'
                resp.resParams['status']='SUCCESS'
                resp.resParams['customer_id'] = req.reqParams['customer_id']
                resp.resParams['chk_acct'] = chk_acct_num
                resp.resParams['chk_bal'] = chk_acct_bal
                resp.resParams['sav_acct'] = sav_acct_num
                resp.resParams['sav_bal'] = sav_acct_bal
                self.sock.send(resp.toString())
                return SUCCESS

    def get_customer_transactions(self, req):
        transaction_list = []
        print "Function:get_customer_transactions() ==>"
        if "customer_id" not in req.reqParams or \
                req.reqParams["customer_id"] == "" :
            self.send_error('GET_RESPONSE','Invalid Customer ID')
            return ERROR
        else: 
            cur_date = time.strftime("%m/%d/%Y")
            cur_month,cur_day,cur_year = cur_date.split('/')
            print"cur_month = "+str(cur_month)

            sql = "SELECT * FROM TRANSACTION_TABLE"
            print"sql -> "+sql
            try:
                self.cursor.execute(sql)
                for row in self.cursor.fetchall():
                    print"Next Row = "+ str(row)
                    print"req.reqParams['customer_id'] = "+req.reqParams['customer_id']
                    print"row[0] = "+str(row[0])
                    dmonth, ddate, dyear=row[1].split('/')
                    print str(dmonth)+" "+ddate+ " "+dyear
                    if cur_month == dmonth and req.reqParams['customer_id'] == str(row[0]):
                        print"Above row matches criteria"
                        temp_str = "CUSTOMER_ID-"+str(row[0])+" DATE-"+ \
                                str(row[1])+" TIME-"+str(row[2])+" ACCOUNT-"+str(row[3]) \
                                +" TRNSTYPE-"+str(row[4])+" AMOUNT-"+str(row[5]) + \
                                " FROM_ACCT-"+str(row[6])+" TO_ACCT-"+str(row[7])
                        print"temp_str = "+temp_str
                        transaction_list.append(temp_str)
                        print transaction_list

            except Exception as e:
                print e
                self.send_error('GET_RESPONSE', 'Server error: DB operation failed.')
                return ERROR

            resp = Response()
            resp.resType = 'GET_RESPONSE'
            resp.resParams['status']='SUCCESS'
            print "Transaction list = "
            print transaction_list
            trnslist_str = ' '.join(transaction_list)
            print trnslist_str
            resp.resParams['trns_list']=' '.join(transaction_list)
            self.sock.send(resp.toString())
            return SUCCESS



    def get_transaction_record(self, customer_id):
        print"called get_transaction_record()"
        sql = "SELECT * from TRANSACTION_TABLE WHERE CUSTOMER_ID='{x}'".format(x=customer_id) 
        print "sql query ==> " + sql
        try:
            self.cursor.execute(sql)
        except Exception as e:
            print e
            return ERROR

        # fetch results (its a list)
        results = self.cursor.fetchone()
        print "*********************************"
        print results
        print "*********************************"
        if not results:
            print "get_transaction_record():Request failure - Record does not exist"
            return results
        else:
            #print str(results[0])+","+str(results[1])+","+str(results[2])+","  \
             #       +str(results[3])+","+str(results[4])+","+str(results[5])+","+str(results[6])    
            print "get_transaction_record(): results = "
            print results
            print "returning from get_transaction_record()"
            return results


    def get_teller_ids(self, req):
        print"Function: get_teller_ids()==>"
        sql = "SELECT * FROM customer_login WHERE CLIENT_TYPE = \'Teller\'"
        print "sql query ==> " + sql
        try:
            self.cursor.execute(sql)
        except Exception as e:
            print e
            return ERROR

        total_num = 0
        resp = Response()
        resp.resType = 'GET_RESPONSE'
        resp.resParams['status']='SUCCESS'

        # fetch results (its a list)
        for row in self.cursor.fetchall():
            total_num = total_num + 1
            teller = 'teller'+str(total_num)
            resp.resParams[teller] = str(row[0])+"/"+str(row[2])

        print"total_num after loop = " + str(total_num)
        resp.resParams['total_teller_num'] = total_num
        
        self.sock.send(resp.toString())
        return SUCCESS


    def get_teller_profile(self,req):

        print "called get_teller_profile()"
        if "teller_id" not in req.reqParams or \
                req.reqParams["teller_id"] == "" :
            self.send_error('GET_RESPONSE','Invalid Teller ID')
            return ERROR
        else: 
            resp = Response()
            sql = "SELECT * from TELLER_INFO_TABLE WHERE TELLER_ID='{x}'".format(x=req.reqParams["teller_id"]) 
            print "sql query ==> " + sql
            try:
                self.cursor.execute(sql)
            except Exception as e:
                print e
                self.send_error('GET_RESPONSE', 'Server error: DB operation failed.')
                return ERROR

            # fetch results (its a list)
            results = self.cursor.fetchone()
            if not results:
                #print "get_teller_profile():Request failure-Record does not exist"
                self.send_error('GET_RESPONSE','Record does not exist')
                return ERROR
            else:
                #print str(results[0])+","+results[1]+","+results[2]+","+results[3]+ \
                        #","+results[4]+","+results[5]+","+results[6]
                
                resp.resType = 'GET_RESPONSE'
                resp.resParams['status']='SUCCESS'
                resp.resParams['teller_id']=results[0]
                resp.resParams['first_name']=results[1]
                resp.resParams['last_name']=results[2]
                resp.resParams['DOB']=results[3]
                resp.resParams['email']=results[4]
                resp.resParams['phone']=results[5]
                resp.resParams['address']=str(results[6])+","+str(results[7])+","+str(results[8]) \
                        +","+str(results[9])+","+str(results[10])+","+str(results[11])
                self.sock.send(resp.toString())
                return SUCCESS

    def get_month_transactions(self, req):
        # Form a list of transactions (Each transaction is a list)
        # to send it to the client
        transaction_list = []
        print "called get_month_transactions()"
        if "month" not in req.reqParams or \
                req.reqParams["month"] == "" :
            self.send_error('GET_RESPONSE','Invalid month field')
            return ERROR
        else: 
            sql = "SELECT * FROM TRANSACTION_TABLE"
            print"sql -> "+sql
            try:
                self.cursor.execute(sql)
                for row in self.cursor.fetchall():
                    print"Next Row = "+ str(row)
                    dmonth, ddate, dyear=row[1].split('/')
                    if req.reqParams["month"] == dmonth:
                        #sql = "SELECT * FROM TRANSACTION_TABLE WHERE CUSTOMER_ID="+str(row[0])
                        #print"sql -> "+sql
                        #self.cursor.execute(sql)

                        # fetch results (its a list)
                        #results = self.cursor.fetchone()
                        print"Above row matches criteria"
                        temp_str = "CUSTOMER_ID-"+str(row[0])+" DATE-"+ \
                                str(row[1])+" TIME-"+str(row[2])+" ACCOUNT-"+str(row[3]) \
                                +" TRNSTYPE-"+str(row[4])+" AMOUNT-"+str(row[5]) + \
                                " FROM_ACCT-"+str(row[6])+" TO_ACCT-"+str(row[7])
                        print"temp_str = "+temp_str
                        transaction_list.append(temp_str)
                        print transaction_list

            except Exception as e:
                print e
                self.send_error('GET_RESPONSE', 'Server error: DB operation failed.')
                return ERROR

            resp = Response()
            resp.resType = 'GET_RESPONSE'
            resp.resParams['status']='SUCCESS'
            print "Transaction list = "
            #print transaction_list
            trnslist_str = ' '.join(transaction_list)
            print trnslist_str
            resp.resParams['trns_list']=' '.join(transaction_list)
            self.sock.send(resp.toString())
            return SUCCESS


    def send_pdf_statement(self, customer_id_fetched):
	#db = MySQLdb.connect(host="127.0.0.1", user="root", passwd="vaibhav", db="Bank")        
        print"Function:send_pdf_statement() ==>"
	cursor_month = self.db.cursor()
        #date_of_txn = (datetime.datetime.now()).strftime("%Y-%m-%d")
        #time_of_txn = (datetime.datetime.now()).strftime("%H:%M")
        date_of_txn = time.strftime("%Y-%m-%d")
        time_of_txn = time.strftime("%H:%M")
	# 
        cursor_month.execute("SELECT FIRST_NAME, LAST_NAME FROM CUSTOMER_INFO_TABLE \
                WHERE CUSTOMER_ID=%s LIMIT 1" %customer_id_fetched)
        tup_name = cursor_month.fetchone()
        first_name = tup_name[0]
        last_name = tup_name[1]
        customer_name = first_name + " " + last_name

        cursor_month.execute("SELECT CHECKING_ACCOUNT_NUM,SAVING_ACCOUNT_NUM FROM \
                ACCOUNT_TABLE WHERE CUSTOMER_ID=%s LIMIT 1" %customer_id_fetched)
        tup_name_account = cursor_month.fetchone()
        checking_acct = tup_name_account[0]
        saving_acct = tup_name_account[1]
        cursor_month.execute("SELECT *  FROM TRANSACTION_TABLE WHERE CUSTOMER_ID=%s \
                ORDER BY DATE" %customer_id_fetched)
        tup_fetched_name = cursor_month.fetchall()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial','B',16)
        pdf.cell(5,10,"Monthly statements ")
        pdf.ln(5)
        pdf.cell(5,10,"Name "+'{:>42}'.format(" : ") + customer_name)
        pdf.ln(5)
        pdf.cell(5,10,"Customer ID " + '{:>31}'.format(" : ") + str(customer_id_fetched))
        pdf.ln(5)
        pdf.cell(5,10,"Checking Account Number " + '{:>5}'.format(" : ") + str(checking_acct))
        pdf.ln(5)
        pdf.cell(5,10,"Saving Account Number " + '{:>10}'.format(" : ") + str(saving_acct))
        pdf.ln(5)
        pdf.cell(5,10,"Date of transaction " + '{:>19}'.format(" : ") + date_of_txn)
        pdf.ln(5)
        pdf.cell(5,10,"Time of transaction " + '{:>19}'.format(" : " )+ time_of_txn)
        pdf.ln(5)
        pdf.set_font('Arial','B',12)
        pdf.cell(5,30,"Date of transaction   " + " Time of transaction  " + " From acct number \
                " + " To acct number     " + " Amount ")


        print tup_fetched_name[0][1]
        initial_month_year_of_txn = str(calendar.month_name[int(str(tup_fetched_name[0][1]).split("/")[0])])
        print initial_month_year_of_txn
        date_list = str(tup_fetched_name[0][1]).split("/")
        print date_list
        file_name_prev = str(customer_id_fetched) + "_" + \
                str(calendar.month_name[int(date_list[0])]) + " " + date_list[2]
        print file_name_prev

        for val in tup_fetched_name:

            date_list = str(val[1]).split("/")
            month_year_of_txn = str(calendar.month_name[int(date_list[0])]) + " " + date_list[2]
            file_name = str(customer_id_fetched) + "_" + month_year_of_txn + ".pdf"
            date_of_transfer_txn = val[1]
            time_of_transfer_txn = val[2]
            acct_type = val[3]
            trns_type = val[4]
            from_account_number = val[6]
            to_account_number =val[7]
            amount_txn = val[5]

            
            if initial_month_year_of_txn != str(calendar.month_name[int(date_list[0])]) :
                pdf.output(file_name_prev,'F')
                self.smtpmail(customer_id_fetched,file_name_prev)
                break
            else:
                pdf.ln(5)
                pdf.cell(5,35,'{:>15}'.format(str(date_of_transfer_txn)) + \
                        '{:>18}'.format(str(time_of_transfer_txn)) +  \
                        '{:>20}'.format(str(acct_type))+ \
                        '{:>20}'.format(str(trns_type))+ \
                        '{:>37}'.format(str(from_account_number)) +  \
                        '{:>30}'.format(str(to_account_number))+ \
                        '{:>20}'.format(str(amount_txn)))
                pdf.ln(5)

        pdf.output(file_name,'F')
        self.smtpmail(customer_id_fetched,file_name)
            
        #db.close()
        cursor_month.close()


    def smtpmail(self, customer_id_fetched, file_name):
        cursor = self.db.cursor()
        cursor.execute("SELECT EMAIL_ID FROM CUSTOMER_INFO_TABLE WHERE CUSTOMER_ID = {} ".format(customer_id_fetched))
        to_mail_id = cursor.fetchone()[0]
        print to_mail_id
        msg = MIMEMultipart()

        msg['From'] = 'kgus.bank@gmail.com'
        msg['To'] =  to_mail_id
        msg['Subject'] = "KGUS BANK ONLINE STATEMENT"

        body = "Dear customer:" \
               "\n\nYou can see the latest statement for your account." \
               "\n\nSincerely," \
               "\nKgus bank Team"

        msg.attach(MIMEText(body, 'plain'))


        attachment = open(file_name, "rb")

        part = MIMEBase('application', 'octet-stream')
        part.set_payload((attachment).read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', "attachment; filename= %s" % file_name)

        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login('kgus.bank@gmail.com', 'kguskgus')
        text = msg.as_string()
        server.sendmail('kgus.bank@gmail.com', to_mail_id, text)
        server.quit()

    def get_monthly_statement(self,req):
        transaction_list = []
        print "Function:get_monthly_statement() ==>"
        if "customer_id" not in req.reqParams or \
                req.reqParams["customer_id"] == "" :
            self.send_error('GET_RESPONSE','Invalid Customer ID')
            return ERROR
        else: 
            cur_date = time.strftime("%m/%d/%Y")
            cur_month,cur_day,cur_year = cur_date.split('/')
            print"cur_month = "+str(cur_month)

            sql = "SELECT * FROM TRANSACTION_TABLE"
            print"sql -> "+sql
            try:
                self.cursor.execute(sql)
                for row in self.cursor.fetchall():
                    print"Next Row = "+ str(row)
                    print"req.reqParams['customer_id'] = "+req.reqParams['customer_id']
                    print"row[0] = "+str(row[0])
                    dmonth, ddate, dyear=row[1].split('/')
                    print str(dmonth)+" "+ddate+ " "+dyear
                    if cur_month == dmonth and req.reqParams['customer_id'] == str(row[0]):
                        print"Above row matches criteria"
                        temp_str = "CUSTOMER_ID-"+str(row[0])+" DATE-"+ \
                                str(row[1])+" TIME-"+str(row[2])+" ACCOUNT-"+str(row[3]) \
                                +" TRNSTYPE-"+str(row[4])+" AMOUNT-"+str(row[5]) + \
                                " FROM_ACCT-"+str(row[6])+" TO_ACCT-"+str(row[7])
                        #print"temp_str = "+temp_str
                        transaction_list.append(temp_str)
                        #print transaction_list


            except Exception as e:
                print e
                self.send_error('GET_RESPONSE', 'Server error: DB operation failed.')
                return ERROR

            resp = Response()
            resp.resType = 'GET_RESPONSE'
            resp.resParams['status']='SUCCESS'
            print "Transaction list = "
            print transaction_list
            trnslist_str = ' '.join(transaction_list)
            print trnslist_str
            resp.resParams['trns_list']=' '.join(transaction_list)
            self.sock.send(resp.toString())

            
            print"calling send_pdf"
            self.send_pdf_statement(req.reqParams["customer_id"] )
            return SUCCESS

    #################################  UPDATE FUNCTIONS  ###############################

    def update_customer_acct(self, req):
        print"called update_customer_acct()"
        if 'customer_id' not in req.reqParams or \
                req.reqParams['customer_id'] == "" or \
                'chk_acct_num' not in req.reqParams or \
                req.reqParams['chk_acct_num'] == "" or \
                'op_type' not in req.reqParams or \
                req.reqParams['op_type'] == "" or \
                'amt' not in req.reqParams or \
                req.reqParams['amt'] == "":
            self.send_error('UPDATE_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        
        amt = req.reqParams['amt']
        amt = float(amt)
        if req.reqParams['subreq_type'] == 'UPDATE_CHK_ACCT':
            acct, bal = self.get_customer_chk_acct(req.reqParams['customer_id'])
        else:
            acct, bal = self.get_customer_sav_acct(req.reqParams['customer_id'])
        bal = float(bal)
        if(req.reqParams['op_type'] == 'SUBTRACT'):
            trns_type = 'WITHDRAW'
            bal = bal - amt
            if bal < 10:
                # send update failure
                self.send_error('UPDATE_RESPONSE', 'Minimum balance should be $10')
                return ERROR
        elif(req.reqParams['op_type'] == 'ADD'):
            trns_type = 'DEPOSIT'
            bal = bal + amt
        else:
            self.send_error('UPDATE_RESPONSE', 'Unknown operation type sent')
            return ERROR
    
        if req.reqParams['subreq_type'] == 'UPDATE_CHK_ACCT':
            acct_type = 'CHECKING'
            sql = "UPDATE ACCOUNT_TABLE SET CHECKING_ACCOUNT_BAL = '{x}' WHERE CHECKING_ACCOUNT_NUM ='{y}'".format(x=bal, y=acct)
        else:
            acct_type = 'SAVING'
            sql = "UPDATE ACCOUNT_TABLE SET SAVING_ACCOUNT_BAL = '{x}' WHERE SAVING_ACCOUNT_NUM ='{y}'".format(x=bal, y=acct)
        print "sql query ==> " + sql
        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            print "UPDATE request failure: server side error"
            self.db.rollback()
            self.send_error('UPDATE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'UPDATE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        print"User ACCOUNT record updated successfully"

        status = self.insert_transaction_record(req.reqParams['customer_id'],trns_type,acct_type,amt,"","")#acct,req.reqParams['to_acct'])
        #status = self.update_transactions(req.reqParams['customer_id'],trns_type,acct_type,amt)
        return status



    def update_customer_profile(self,req):
        print"called update_customer_profile()"
        if 'customer_id' not in req.reqParams or \
                req.reqParams['customer_id'] == "":
            self.send_error('UPDATE_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        elems = []
        if 'first_name' in req.reqParams and req.reqParams['first_name'] != '':
            elems.append("FIRST_NAME='{}'".format(req.reqParams['first_name']))
            print elems
        if 'last_name' in req.reqParams and req.reqParams['last_name'] != '':
            elems.append("LAST_NAME='{}'".format(req.reqParams['last_name']))
            print elems
        if 'DOB' in req.reqParams and req.reqParams['DOB'] != '':
            elems.append("DATE_OF_BIRTH='{}'".format(req.reqParams['DOB']))
            print elems
        if 'email' in req.reqParams and req.reqParams['email'] != '':
            elems.append("EMAIL_ID='{}'".format(req.reqParams['email']))
            print elems
        if 'phone' in req.reqParams and req.reqParams['phone'] != '':
            elems.append("PHONE_NUMBER='{}'".format(req.reqParams['phone']))
            print elems
        if 'apt_num' in req.reqParams and req.reqParams['apt_num'] != '':
            elems.append("APT_NUM='{}'".format(req.reqParams['apt_num']))
            print elems
        if 'street_name' in req.reqParams and req.reqParams['street_name']:
            elems.append("STREET_NAME='{}'".format(req.reqParams['street_name']))
            print elems
        if 'city' in req.reqParams and req.reqParams['city'] != '':
            elems.append("CITY='{}'".format(req.reqParams['city']))
            print elems
        if 'state' in req.reqParams and req.reqParams['state'] != '':
            elems.append("STATE='{}'".format(req.reqParams['state']))
            print elems
        if 'country' in req.reqParams and req.reqParams['country'] != '':
            elems.append("COUNTRY='{}'".format(req.reqParams['country']))
            print elems
        if 'zipcode' in req.reqParams and req.reqParams['zipcode']:
            elems.append("ZIPCODE='{}'".format(req.reqParams['zipcode']))
            print elems
        if 'gender' in req.reqParams and req.reqParams['gender']:
            elems.append("GENDER='{}'".format(req.reqParams['gender']))
            print elems

        updates = ','.join(elems)
        print "elements Joined:" + updates
        sql = "UPDATE CUSTOMER_INFO_TABLE SET {e} WHERE \
                CUSTOMER_ID ='{y}'".format(e=updates, y=req.reqParams['customer_id'])
        print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "UPDATE request failure: server side error"
            self.db.rollback()
            self.send_error('UPDATE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'UPDATE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS



    def transfer_money(self, req):
        
        print"transfer_money(): ==>"
        if 'to_bank' not in req.reqParams or \
                req.reqParams['to_bank'] == "" or \
                'to_acct' not in req.reqParams or \
                req.reqParams['to_acct'] == "":
            self.send_error('UPDATE_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        if(req.reqParams['acct_type'] == 'checking'):
            req.reqParams['subreq_type'] = 'UPDATE_CHK_ACCT'
            print "transfer_money(): subrequest = UPDATE_CHK_ACCT & acct_type = checking"
        else:
            print"transfer_money(): inside else block"
            print "acct_type set to " + req.reqParams['acct_type']
            req.reqParams['subreq_type'] = 'UPDATE_SAV_ACCT'

        # Here goes the code to take care of to_acct and to_bank
        # Now update user account
        trns_type = 'TRANSFER'
        self.update_user_acct(req, trns_type)


    def update_user_acct(self, req, trns_type):

        print"update_user_acct() ==> "
        if 'customer_id' not in req.reqParams or \
                req.reqParams['customer_id'] == "" or \
                'chk_acct_num' not in req.reqParams or \
                req.reqParams['chk_acct_num'] == "" or \
                'op_type' not in req.reqParams or \
                req.reqParams['op_type'] == "" or \
                'amt' not in req.reqParams or \
                req.reqParams['amt'] == "":
            self.send_error('UPDATE_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        
        amt = req.reqParams['amt']
        amt = float(amt)
        if req.reqParams['subreq_type'] == 'UPDATE_CHK_ACCT':
            acct, bal = self.get_customer_chk_acct(req.reqParams['customer_id'])
            print "acct = "+ str(acct) + " bal = "+ str(bal)
        else:
            acct, bal = self.get_customer_sav_acct(req.reqParams['customer_id'])
            print "acct = "+ str(acct) + " bal = "+ str(bal)

        bal = float(bal)
        if(req.reqParams['op_type'] == 'SUBTRACT'):
            #trns_type = 'WITHDRAW'
            bal = bal - amt
            if bal < 10:
                # send update failure
                self.send_error('UPDATE_RESPONSE', 'Minimum balance should be $10')
                return ERROR
        elif(req.reqParams['op_type'] == 'ADD'):
            #trns_type = 'DEPOSIT'
            bal = bal + amt
        else:
            self.send_error('UPDATE_RESPONSE', 'Unknown operation type sent')
            return ERROR
    
        if req.reqParams['subreq_type'] == 'UPDATE_CHK_ACCT':
            print"acct_type getting set to CHECKING"
            acct_type = 'CHECKING'
            sql = "UPDATE ACCOUNT_TABLE SET CHECKING_ACCOUNT_BAL = '{x}' WHERE CHECKING_ACCOUNT_NUM ='{y}'".format(x=bal, y=acct)
        else:
            print "acct_type getting set to SAVIG"
            acct_type = 'SAVING'
            sql = "UPDATE ACCOUNT_TABLE SET SAVING_ACCOUNT_BAL = '{x}' WHERE SAVING_ACCOUNT_NUM ='{y}'".format(x=bal, y=acct)
        print "sql query ==> " + sql
        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            print "UPDATE request failure: server side error"
            self.db.rollback()
            self.send_error('UPDATE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR

        resp = Response()
        resp.resType = 'UPDATE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        print"User ACCOUNT record updated successfully"
        print"Before calling insert transaction record: (trns_type,acct_type,amt,acct,to_actt) "+ \
                str(trns_type)+" "+str(acct_type)+" "+str(amt)+" "+str(acct)
        status = self.insert_transaction_record(req.reqParams['customer_id'],trns_type,acct_type,amt,acct,req.reqParams['to_acct'])
        return #status





    def update_teller_profile(self,req):
        print"called update_teller_profile()"
        if 'teller_id' not in req.reqParams or \
                req.reqParams['teller_id'] == "":
            self.send_error('UPDATE_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        elems = []
        if 'first_name' in req.reqParams and req.reqParams['first_name'] != '':
            elems.append("FIRST_NAME='{}'".format(req.reqParams['first_name']))
            print elems
        if 'last_name' in req.reqParams and req.reqParams['last_name'] != '':
            elems.append("LAST_NAME='{}'".format(req.reqParams['last_name']))
            print elems
        if 'DOB' in req.reqParams and req.reqParams['DOB'] != '':
            elems.append("DATE_OF_BIRTH='{}'".format(req.reqParams['DOB']))
            print elems
        if 'email' in req.reqParams and req.reqParams['email'] != '':
            elems.append("EMAIL_ID='{}'".format(req.reqParams['email']))
            print elems
        if 'phone' in req.reqParams and req.reqParams['phone'] != '':
            elems.append("PHONE_NUMBER='{}'".format(req.reqParams['phone']))
            print elems
        if 'apt_num' in req.reqParams and req.reqParams['apt_num'] != '':
            elems.append("APT_NUM='{}'".format(req.reqParams['apt_num']))
            print elems
        if 'street_name' in req.reqParams and req.reqParams['street_name']:
            elems.append("STREET_NAME='{}'".format(req.reqParams['street_name']))
            print elems
        if 'city' in req.reqParams and req.reqParams['city'] != '':
            elems.append("CITY='{}'".format(req.reqParams['city']))
            print elems
        if 'state' in req.reqParams and req.reqParams['state'] != '':
            elems.append("STATE='{}'".format(req.reqParams['state']))
            print elems
        if 'country' in req.reqParams and req.reqParams['country'] != '':
            elems.append("COUNTRY='{}'".format(req.reqParams['country']))
            print elems
        if 'zipcode' in req.reqParams and req.reqParams['zipcode']:
            elems.append("ZIPCODE='{}'".format(req.reqParams['zipcode']))
            print elems
        if 'gender' in req.reqParams and req.reqParams['gender']:
            elems.append("GENDER='{}'".format(req.reqParams['gender']))
            print elems

        updates = ','.join(elems)
        print "elements Joined:" + updates
        sql = "UPDATE TELLER_INFO_TABLE SET {e} WHERE \
                TELLER_ID ='{y}'".format(e=updates, y=req.reqParams['teller_id'])
        print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "UPDATE request failure: server side error"
            self.db.rollback()
            self.send_error('UPDATE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'UPDATE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS
    ##################################  INSERT FUNCTIONS  ####################################

    def insert_login_record(self, req):
        print"called insert_login_record()"
        if 'user_name' not in req.reqParams or \
                'password' not in req.reqParams or \
                'customer_id' not in req.reqParams or \
                'record_client_type' not in req.reqParams or \
                req.reqParams['user_name'] == "" or \
                req.reqParams['password'] == "" or \
                req.reqParams['customer_id'] == "" or \
                req.reqParams['record_client_type'] == "":
            self.send_error('INSERT_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        sql = "INSERT INTO customer_login(USERNAME,PASSWORD,CUSTOMER_ID,CLIENT_TYPE) \
                VALUES('{a}',MD5('{b}'),'{c}','{d}')".format(a=req.reqParams['user_name'], \
                b=req.reqParams['password'], c=req.reqParams['customer_id'], \
                d = req.reqParams['record_client_type'])
        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "INSERT request failure: server side error"
            self.db.rollback()
            self.send_error('INSERT_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'INSERT_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS

    def insert_accounts_record(self, req):
        print"called insert_accounts_record()"
        if 'customer_id' not in req.reqParams or \
                'customer_chk_acct' not in req.reqParams or \
                'customer_sav_acct' not in req.reqParams or \
                'customer_chk_bal' not in req.reqParams or \
                'customer_sav_bal' not in req.reqParams or \
                req.reqParams['customer_id'] == "" or \
                req.reqParams['customer_chk_acct'] == "" or \
                req.reqParams['customer_sav_acct'] == "" or \
                req.reqParams['customer_chk_bal'] == "" or \
                req.reqParams['customer_sav_bal'] == "":
            self.send_error('INSERT_RESPONSE','Multiple Invalid key-value entries')
            return ERROR
        sql = "INSERT INTO ACCOUNT_TABLE(CUSTOMER_ID, CHECKING_ACCOUNT_NUM, SAVING_ACCOUNT_NUM, \
                CHECKING_ACCOUNT_BAL, SAVING_ACCOUNT_BAL) VALUES('{a}','{b}','{c}','{d}','{e}')".format \
                (a=req.reqParams['customer_id'],b=req.reqParams['customer_chk_acct'], \
                c=req.reqParams['customer_sav_acct'],d=req.reqParams['customer_chk_bal'], \
                e=req.reqParams['customer_sav_bal'])
        #print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "INSERT request failure: server side error"
            self.db.rollback()
            self.send_error('INSERT_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'INSERT_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS

    def insert_profile_record(self, req):
        print "called insert_profile_record()"
        if 'first_name' not in req.reqParams or 'last_name' not in req.reqParams or \
                'DOB' not in req.reqParams or 'email' not in req.reqParams or \
                'phone' not in req.reqParams or 'apt_num' not in req.reqParams \
                or 'street_name' not in req.reqParams or 'city' not in req.reqParams or \
                'state' not in req.reqParams or 'country' not in req.reqParams or \
                'zipcode' not in req.reqParams or 'gender' not in req.reqParams or \
                req.reqParams['first_name'] == "" or req.reqParams['last_name'] == "" or \
                req.reqParams['DOB'] == "" or req.reqParams['email'] == "" or \
                req.reqParams['phone'] == "" or req.reqParams['apt_num'] == "" \
                or req.reqParams['street_name'] == "" or req.reqParams['city'] == "" or \
                req.reqParams['state'] == "" or req.reqParams['country'] == "" or \
                req.reqParams['zipcode'] == "" or req.reqParams['gender'] == "":
            self.send_error('INSERT_RESPONSE','Multiple Invalid key-value entries')
            return ERROR

        if 'customer_id' in req.reqParams:
            print"in customer_id block"
            sql = "INSERT INTO CUSTOMER_INFO_TABLE(CUSTOMER_ID, FIRST_NAME, LAST_NAME, \
                    DATE_OF_BIRTH, EMAIL_ID,PHONE_NUMBER,APT_NUM,STREET_NAME,CITY,STATE, \
                    COUNTRY, ZIPCODE, GENDER) VALUES('{a}','{b}','{c}','{d}','{e}','{f}', \
                    '{g}','{h}','{i}','{j}','{k}','{l}','{m}')".format(a=req.reqParams['customer_id'], \
                    b=req.reqParams['first_name'], c=req.reqParams['last_name'] ,\
                    d=req.reqParams['DOB'],e=req.reqParams['email'], f=req.reqParams['phone'], \
                    g=req.reqParams['apt_num'], h=req.reqParams['street_name'], \
                    i=req.reqParams['city'], j=req.reqParams['state'], k=req.reqParams['country'], \
                    l=req.reqParams['zipcode'], m=req.reqParams['gender'])
            print "sql -> "+sql
        elif 'teller_id' in req.reqParams:
            print"in teller id block"
            sql = "INSERT INTO TELLER_INFO_TABLE(TELLER_ID, FIRST_NAME, LAST_NAME, \
                    DATE_OF_BIRTH, EMAIL_ID,PHONE_NUMBER,APT_NUM,STREET_NAME,CITY,STATE, \
                    COUNTRY, ZIPCODE, GENDER) VALUES('{a}','{b}','{c}','{d}','{e}','{f}', \
                    '{g}','{h}','{i}','{j}','{k}','{l}','{m}')".format(a=req.reqParams['teller_id'], \
                    b=req.reqParams['first_name'], c=req.reqParams['last_name'] ,\
                    d=req.reqParams['DOB'],e=req.reqParams['email'], f=req.reqParams['phone'], \
                    g=req.reqParams['apt_num'], h=req.reqParams['street_name'], \
                    i=req.reqParams['city'], j=req.reqParams['state'], k=req.reqParams['country'], \
                    l=req.reqParams['zipcode'], m=req.reqParams['gender'])
            print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "INSERT request failure: server side error"
            self.db.rollback()
            self.send_error('INSERT_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'INSERT_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS

    def insert_transaction_record(self,customer_id,trns_type,acct_type,amount,from_acct,to_acct):
        print"insert_transaction_record() ==>"
    
        cur_date = time.strftime("%m/%d/%Y")
        #print date
        cur_time = time.strftime("%X") 
        #print cur_time
        cur_time = cur_time.replace(':', '.')
        #print cur_time
        
        sql = "INSERT INTO TRANSACTION_TABLE(CUSTOMER_ID,DATE,TIME,ACCOUNT_TYPE, \
                TRNS_TYPE,AMOUNT,FROM_ACCT,TO_ACCT) \
                VALUES('{a}','{b}','{c}','{d}','{e}','{f}','{g}','{h}')".format( \
                a=customer_id, b=cur_date,c=cur_time, d=acct_type, e=trns_type,f=amount, \
                g=from_acct, h=to_acct)
        print "insert transaction record sql ==>" + sql
        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "INSERT request failure: server side error"
            self.db.rollback()
            return ERROR
           
        print"Transaction record updated successfully"
        return SUCCESS
    #################################   DELETE FUNCTIONS  ################################

    def delete_login_record(self, req):
        print"called delete_login_record()"
        if "customer_id" not in req.reqParams or \
                req.reqParams["customer_id"] == "" :
            self.send_error('DELETE_RESPONSE','Invalid Customer ID')
            return ERROR
        
        sql = "DELETE FROM customer_login WHERE CUSTOMER_ID='{a}'".format \
                (a=req.reqParams['customer_id'])
        #print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "DELETE request failure: server side error"
            self.db.rollback()
            self.send_error('DELETE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'DELETE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS


    def delete_accounts_record(self, req):
        print"called delete_accounts_record()"
        if "customer_id" not in req.reqParams or \
                req.reqParams["customer_id"] == "" :
            self.send_error('DELETE_RESPONSE','Invalid Customer ID')
            return ERROR
        sql = "DELETE FROM ACCOUNT_TABLE WHERE CUSTOMER_ID='{a}'".format \
                (a=req.reqParams['customer_id'])
        #print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "DELETE request failure: server side error"
            self.db.rollback()
            self.send_error('DELETE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'DELETE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        return SUCCESS

    def delete_profile_record(self, req):
        print"\ndelete_profile_record()"
        if "customer_id" in req.reqParams:
            print "customer id in request ==> "
            if req.reqParams["customer_id"] == "" :
                self.send_error('DELETE_RESPONSE','Invalid Customer ID')
                return ERROR
            
            sql = "DELETE FROM CUSTOMER_INFO_TABLE WHERE CUSTOMER_ID='{a}'".format \
                (a=req.reqParams['customer_id'])
        elif "teller_id" in req.reqParams:
            print "teller id in request ==> "
            if req.reqParams["teller_id"] == "":
                self.send_error('DELETE_RESPONSE', 'Invalid Teller ID')
                return ERROR
            sql = "DELETE FROM TELLER_INFO_TABLE WHERE TELLER_ID='{a}'".format \
                (a=req.reqParams['teller_id'])

        print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            print "DELETE request failure: server side error"
            self.db.rollback()
            self.send_error('DELETE_RESPONSE', 'Server error: DB operation could not be completed')
            return ERROR
            
        resp = Response()
        resp.resType = 'DELETE_RESPONSE'
        resp.resParams['status']='SUCCESS'
        self.sock.send(resp.toString())
        print"profile successfully deleted\n"
        return SUCCESS

    def delete_transaction_record(self, customer_id):
        print"called delete_transaction_record()"
        sql = "DELETE FROM TRANSACTION_TABLE WHERE CUSTOMER_ID='{a}'".format(a=customer_id)
        #print "sql -> "+sql

        try:
            self.cursor.execute(sql)
            self.db.commit()
        except Exception as e:
            print e
            #print "DELETE request failure: server side error"
            self.db.rollback()
            return ERROR
        
        print"delete_transaction_record(): Record deleted successfully"
        return SUCCESS

#########################  SERVER CLASS #########################  
    
class Server(threading.Thread):
    def __init__(self, family, host, port):
        # store input values for future reference
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.clientThreads = []

        # create new server socket and bind to host:port
        self.ssock = socket.socket(family)
        self.ssock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ssock.bind((self.ssock.getsockname()[0], port))
        #self.ssock.settimeout(30)
        self.ssock.listen(5)
#---------------------------------------------------------------------------------------------------
        # To enable SSL uncomment ssl.wrap_socket() call
        # Wrap Socket with SSL/TLS encryption function
        # cert generated with openssl req -new -x509 -days 365 -nodes -out cert.pem -keyout cert.pem
        self.sslSock = ssl.wrap_socket(self.ssock, \
                ssl_version=ssl.PROTOCOL_TLSv1, server_side=True, certfile="./cert.pem")
#---------------------------------------------------------------------------------------------------
        

    def run(self):
        while True:
            print "Server Listening for Clients.."

            # c,addr is a <connected_socket , client_address> tuple
#------------------------------------------------------
            # To enable SSL uncomment this line
	    cliSock, cliAddr = self.sslSock.accept()
#------------------------------------------------------
            # To disable SSL uncomment this line
            #cliSock, cliAddr = self.ssock.accept()
#------------------------------------------------------
            print "======>>>>>>>>  New Client request accepted from: [" + str(cliAddr) + "]"
            cli = Client(cliSock, cliAddr)
            cli.setDaemon(True)
            cli.start()


#########################  MAIN  #########################  
def main():
    host = '127.0.0.1'
    port = 5500

    # Create DataBase object
    server = Server(socket.AF_INET, "0.0.0.0", port)
    #server.start()

    #server = Server(socket.AF_INET6, "::", port)
    server.setDaemon(True)
    server.start()

    while True:
        time.sleep(10)

if __name__=='__main__':
    main()

