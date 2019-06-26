import edap, platform, threading, redis
from flask import Flask, jsonify, make_response, request, abort
from flask import __version__ as _flaskVersion
from flask_cors import CORS
from hashlib import md5 as _MD5HASH
from hashlib import sha256 as _SHA256HASH
from copy import deepcopy
from time import sleep
from random import randint
from json import loads as _jsonLoad
from json import dumps as _jsonConvert
from functools import wraps
from os import environ
from multiprocessing import Value
from sys import exit as _exit

from types import ModuleType, FunctionType
from gc import get_referents
from sys import getsizeof

ALLOW_DEV_ACCESS = True

api_version = "1.1-dev"

#server_header = "eDAP/%s eDAP-API/%s Flask/%s" % (edap.edap_version, api_version, _flaskVersion)

#class localFlask(Flask):
#	def process_response(self, response):
#		response.headers['Server'] = server_header
#		super(localFlask, self).process_response(response)
#		return response

BLACKLIST = type, ModuleType, FunctionType
def getsize(obj):
	if isinstance(obj, BLACKLIST):
		return None
	seen_ids = set()
	size = 0
	objects = [obj]
	while objects:
		need_referents = []
		for obj in objects:
			if not isinstance(obj, BLACKLIST) and id(obj) not in seen_ids:
				seen_ids.add(id(obj))
				size += getsizeof(obj)
				need_referents.append(obj)
		objects = get_referents(*need_referents)
	return size

try:
	privUsername = environ["NETRIX_DEV_USER"]
	privPassword = environ["NETRIX_DEV_PASW"]
except:
	privUsername = None
	privPassword = None
	ALLOW_DEV_ACCESS = False

app = Flask("EDAP-API")
CORS(app)

r = redis.Redis(host='localhost', port=6379, db=0)

def getData(token):
	 return _jsonLoad(r.get("token:" + token).decode("utf-8"))

def getTokens():
	return [i.decode('utf-8').replace("token:", "") for i in r.keys('token:*')]

def getLogins(logintype):
	try:
		return Value('i', int(r.get("logincounter:" + logintype)))
	except TypeError:
		print("TypeError for getLogins")
		r.set("logincounter:" + logintype, 0)
		return 0
	except redis.exceptions.ConnectionError:
		# This is one of the first connections to the database, so we can handle connection errors here
		print("Database connection failed!")
		_exit(1)

def userInDatabase(token):
	return "token:" + token in [i.decode('utf-8') for i in r.keys('token:*')]

def classIDExists(token, cid):
	return cid in range(len(getData(token)['data']))

def subjectIDExists(token, cid, sid):
	return sid in range(len(getData(token)['data']['classes'][cid]['subjects']))

class PeriodicAnalyticsSave(threading.Thread):
	def run(self):
		while True:
			r.set("logincounter:full", logins_full.value)
			r.set("logincounter:fast", logins_fast.value)
			r.set("logincounter:fail:generic", logins_fail_ge.value)
			r.set("logincounter:fail:password", logins_fail_wp.value)
			sleep(5)

class PeriodicDatabaseSaveToDisk(threading.Thread):
	def run(self):
		while True:
			r.save()
			sleep(120)

logins_full = getLogins("full")
logins_fast = getLogins("fast")
logins_fail_ge = getLogins("fail:generic")
logins_fail_wp = getLogins("fail:password")

threads = {}

threads["analytics"] = PeriodicAnalyticsSave()
threads["analytics"].start()
threads["database"] = PeriodicDatabaseSaveToDisk()
threads["database"].start()

def hashString(inp):
	return _MD5HASH(inp.encode()).hexdigest()

def hashPassword(inp):
	return _SHA256HASH(inp.encode()).hexdigest()

class DataPopulationThread(threading.Thread):
	def __init__(self):
		self.status = None
		super().__init__()

def periodicDataUpdate(user_token):
	while True:
		sleep(randint(1200, 3600))
		users[user_token]['data'] = populateData(users[user_token]['object'])

def populateData(obj=None, username=None, password=None):
	"""
		Fill in the 'data' part of the user dict. This will contain subjects, grades, etc.
	"""
	dataDict = {'classes':None, 'tests':None}
	try:
		#self.status = {"status":"S_CLASSES","progress":None}
		cl = obj.getClasses()
	except Exception as e:
		print('PDATA || Error getting classes: %s' % e)
		abort(500)

	output = cl
	try:
		output[0]['subjects'] = obj.getSubjects(0)
	except Exception as e:
		print('PDATA || Error getting subjects for class')
		output[0]['subjects'] = None
	for z in range(len(output[0]['subjects'])):
		#self.status = {"status":"S_GRADES", "progress":"%s/%s" % (z+1, len(output[x]['subjects'])+1)}
		output[0]['subjects'][z]['id'] = z
		try:
			output[0]['subjects'][z]['grades'] = obj.getGradesForSubject(0, z)
		except Exception as e:
			print('PDATA || Error getting grades for subject %s: %s' % (z, e))
			output[0]['subjects'][z]['grades'] = None
			continue
	#self.status = {'status':'S_DONE', 'progress':None}
	dataDict['classes'] = output
	print("POPLD || dataDict is %s bytes" % getsize(dataDict))
	return dataDict

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == privUsername and hashPassword(password) == privPassword

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return make_response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.errorhandler(404)
def e404(err):
	return make_response(jsonify({'error':'E_UNKNOWN_ENDPOINT'}), 404)

@app.errorhandler(401)
def e401(err):
	return make_response(jsonify({'error':'E_TOKEN_NONEXISTENT'}), 401)

@app.errorhandler(400)
def e400(err):
	return make_response(jsonify({'error':'E_INVALID_DATA'}), 400)

@app.errorhandler(405)
def e405(err):
	return make_response(jsonify({'error':'E_INVALID_METHOD'}), 405)

@app.errorhandler(500)
def e500(err):
	return make_response(jsonify({'error':'E_SERVER_ERROR'}), 500)

@app.route('/', methods=["GET"])
def index():
	return make_response(jsonify({'name':'eDnevnikAndroidProject', 'version':edap.edap_version, 'host-os':platform.system()+' '+platform.version(),'flask-version':_flaskVersion}), 200)

@app.errorhandler(redis.exceptions.ConnectionError)
def exh_RedisDatabaseFailure(e):
	return make_response(jsonify({'error':'E_DATABASE_CONNECTION_FAILED'}), 500)

@app.route('/dev/info', methods=["GET"])
@requires_auth
def info():
	if ALLOW_DEV_ACCESS:
		return '<!DOCTYPE html><html><head><title>eDAP dev info</title></head><body><h1>eDAP dev info</h1><h2>Tokens</h2><pre>%s</pre><h2>Logins</h2><h3>Successful</h3><p>Full (with data fetch): %i</p><p>Fast (data cached): %i</p><h3>Failed</h3><p>Wrong password: %i</p><p>Generic (bad JSON, library exception etc.): %i</p></body></html>' % ('\n'.join(getTokens()), logins_full.value, logins_fast.value, logins_fail_wp.value, logins_fail_ge.value)
	else:
		abort(404)

@app.route('/dev/threads', methods=["GET"])
@requires_auth
def threadList():
	if ALLOW_DEV_ACCESS:
		return '<!DOCTYPE html><html><head><title>eDAP dev thread info</title></head><body><h1>eDAP thread info</h1><h2>List</h2><pre>%s</pre></body></html>' % '\n'.join(threads.keys())
	else:
		abort(404)

@app.route('/dev/threads/<string:threadname>', methods=["GET"])
@requires_auth
def threadInfo(threadname):
	if ALLOW_DEV_ACCESS:
		if threadname not in threads:
			return make_response('Thread does not exist', 404)
		return '<!DOCTYPE html><html><head><title>eDAP dev thread info</title></head><body><h1>eDAP thread info</h1><pre>isAlive: %s</pre></body></html>' % threads[threadname].isAlive()
	else:
		abort(404)

@app.route('/dev/info/tokendebug/<string:token>', methods=["GET"])
@requires_auth
def tokenDebug(token):
	if ALLOW_DEV_ACCESS:
		return '<!DOCTYPE html><html><head><title>eDAP dev token debug</title></head><body><h1>eDAP token debug</h1><pre>%s</pre></body></html>' % _jsonConvert(getData(token), indent=4, sort_keys=True)
	else:
		abort(404)

@app.route('/api/login', methods=["POST"])
def login():
	if not request.json or not 'username' in request.json or not 'password' in request.json:
		print("LOGIN || Invalid JSON [%s]" % request.data)
		logins_fail_ge.value += 1
		abort(400)
	token = hashString(request.json["username"] + ":" + request.json["password"])
	if userInDatabase(token):
		logins_fast.value += 1
		return make_response(jsonify({'token':token}), 200)
	print("LOGIN || Attempting to log user %s in..." % request.json['username'])
	try:
		obj = edap.edap(request.json["username"], request.json["password"])
	except edap.WrongCredentials:
		print("LOGIN || Failed for user %s, invalid credentials." % request.json["username"])
		logins_fail_wp.value += 1
		return make_response(jsonify({'error':'E_INVALID_CREDENTIALS'}), 401)
	except edap.FatalLogExit:
		print("LOGIN || Failed for user %s, program error." % request.json["username"])
		logins_fail_ge.value += 1
		abort(500)
	print("LOGIN || Success for user %s, saving to Redis - token is %s." % (request.json["username"], token))
	dataObj = {'user':request.json["username"], 'pasw':request.json["password"], 'data':populateData(obj), 'periodic_updates':0}
	r.set('token:' + token, _jsonConvert(dataObj))
	logins_full.value += 1
	return make_response(jsonify({'token':token}), 200)

@app.route('/api/user/<string:token>/classes', methods=["GET"])
def getClasses(token):
	if not userInDatabase(token):
		print('CLASS || Token %s does not exist' % token)
		abort(401)
	o = getData(token)['data']
	for i in o['classes']:
		try:
			del i['subjects']
		except:
			pass
	return make_response(jsonify(o), 200)

@app.route('/api/user/<string:token>/classes/<int:class_id>/subjects', methods=["GET"])
def getSubjects(token, class_id):
	if not userInDatabase(token) or not classIDExists(token, class_id):
		print('SUBJS || Either token (%s) or class ID (%s) is invalid' % (token, class_id))
		abort(401)
	o = getData(token)['data']['classes'][class_id]['subjects']
	for i in o:
		del i['grades']
	return make_response(jsonify({'subjects': o}), 200)

@app.route('/api/user/<string:token>/classes/<int:class_id>/subjects/<int:subject_id>', methods=["GET"])
def getSpecSubject(token, class_id, subject_id):
	if not userInDatabase(token) or not classIDExists(token, class_id) or not subjectIDExists(token, class_id, subject_id):
		print('SPSBJ || Either token (%s), class ID (%s) or subject ID (%s) is invalid' % (token, class_id, subject_id))
		abort(401)
	o = getData(token)['data']['classes'][class_id]['subjects'][subject_id]
	del o['grades']
	return make_response(jsonify(o), 200)

@app.route('/api/user/<string:token>/classes/<int:class_id>/subjects/<int:subject_id>/grades', methods=["GET"])
def getGrades(token, class_id, subject_id):
	if not userInDatabase(token) or not classIDExists(token, class_id) or not subjectIDExists(token, class_id, subject_id):
		print('GRADE || Either token (%s), class ID (%s) or subject ID (%s) is invalid' % (token, class_id, subject_id))
		abort(401)
	o = getData(token)['data']['classes'][class_id]['subjects'][subject_id]['grades']
	lgrades = []
	for i in o:
		lgrades.append(i['grade'])
	avg = round(sum(lgrades)/len(lgrades), 2)
	return make_response(jsonify({'grades': o, 'average': avg}), 200)

if __name__ == '__main__':
	app.run(debug=True, host="0.0.0.0")