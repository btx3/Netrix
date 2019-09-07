import logging, redis, edap, requests
from hashlib import md5 as _MD5HASH
from hashlib import sha256 as _SHA256HASH
from json import loads as _jsonLoad
from json import dumps as _jsonConvert
from copy import deepcopy
from random import randint
from random import choice as _randomChoice
from sys import exit as _sysExit
from math import floor as _mFloor
from math import log as _mLog
from math import pow as _mPow
from os import environ
from os.path import exists as _fileExists
from os.path import join as _joinPath
from os.path import getsize as _getFileSize
from pyfcm import FCMNotification
from threading import Thread
from time import sleep
from time import time as _time
from time import clock as _clock
from string import ascii_letters

log = logging.getLogger(__name__)
_fbPushService = None
_redis = None

_threads = {}

class NonExistentSetting(Exception):
	pass

def get_credentials(token):
	"""
		Call Vault to get the creds for a token.
	"""
	data = requests.get(
		'%s/v1/secret/data/%s' % (config["VAULT_SERVER"], token),
		headers={'X-Vault-Token': config["VAULT_TOKEN_READ"]}
	)
	data.raise_for_status()
	return data.json()["data"]["data"]

def set_credentials(token, username, password):
	"""
		Call Vault to set a credential pair for a token.
	"""
	data = requests.post(
		'%s/v1/secret/data/%s' % (config["VAULT_SERVER"], token),
		headers={'X-Vault-Token': config["VAULT_TOKEN_WRITE"]},
		json={
			"data": {
				"username": username,
				"password": password
			}
		}
	)
	data.raise_for_status()

def rm_credentials(token):
	"""
		Call Vault to remove a credential pair for a token.
	"""
	data = requests.delete(
		'%s/v1/secret/data/%s' % (config["VAULT_SERVER"], token),
		headers={'X-Vault-Token': config["VAULT_TOKEN_WRITE"]}
	)
	data.raise_for_status()

def _exit(exitCode):
	print("!!! Exiting with code %i\n    Check the log file for more information if possible." % exitCode)
	_sysExit(exitCode)

def localize(token, notif_type):
	"""
		Localize a string according to the language reported by
		the phone through /api/stats.
	"""
	locs = {
		"en": {
			"note": "New note",
			"grade": "New grade",
			"absence": "New absence",
			"test": "New test",
			"class": "New class"
		},
		"hr": {
			"note": "Nova bilješka",
			"grade": "Nova ocjena",
			"absence": "Novi izostanak",
			"test": "Novi ispit",
			"class": "Novi razred"
		},
		"de": {
			"note": "New note",
			"grade": "New grade",
			"absence": "New absence",
			"test": "New test",
			"class": "New class"
		},
		"sv": {
			"note": "New note",
			"grade": "New grade",
			"absence": "New absence",
			"test": "New test",
			"class": "New class"
		}
	}
	lang = getData(token)['lang']
	return locs[lang][notif_type]

def random_string(length: int) -> str:
	return ''.join(_randomChoice(ascii_letters) for m in range(length))

def generateTestUser() -> (str, str, str):
	"""
		Generate a user for testing purposes.
	"""
	user = random_string(6)
	pasw = random_string(10)
	token = hashString(user + ":" + pasw)
	data = {
		'ignore_updating': True,
		'data': {
			'classes': [
				{
					"class": "1.a",
					"classmaster": "Razrednik",
					"complete_avg": 4.20,
					"school_city": "Grad",
					"school_name": "Ime škole",
					"year": "2018./2019.",
					"subjects": [
						{
							"average": 4.58,
							"id": 0,
							"professors": ["Netko Netkić", "Nitko Nitkić"],
							"subject": "Hrvatski jezik"
						},
						{
							"average": 5.00,
							"id": 1,
							"professors": ["Netko Netkić"],
							"subject": "Engleski jezik"
						},
						{
							"average": 3.89,
							"id": 1,
							"professors": ["Nitko Nitkić"],
							"subject": "Latinski jezik"
						},
						{
							"average": 4.96,
							"id": 1,
							"professors": ["Ivan Ivanović"],
							"subject": "Fizika"
						}
					],
					"tests": [
						{
							"current": False,
							"date": _time() - 120,
							"id": 0,
							"subject": "Hrvatski",
							"test": "Prvi ispit znanja"
						},
						{
							"current": True,
							"date": _time() + 259200 + 120,
							"id": 1,
							"subject": "Hrvatski",
							"test": "Drugi ispit znanja"
						}
					],
					'info': {
						"address": "Ulica, Mjesto",
						"birthdate": "1. 1. 2000.",
						"birthplace": "Grad, Država",
						"name": "Netko Netkić",
						"number": 1,
						"program": "Program"
					},
					"absences": {"overview":{"awaiting":0,"justified":0,"sum":0,"sum_leftover":0,"unjustified":0}, "full":[]}
				}
			]
		},
		'last_ip': '0.0.0.0',
		'device': {
			'platform': None,
			'model': None
		},
		'lang': None,
		'resolution': None,
		'new': None,
		'generated_with': 'testUser',
		'settings': {
			'notif': {
				'disable': False,
				'ignore': []
			}
		},
		'messages': []
	}
	saveData(token, data)
	set_credentials(token, user, pasw)
	return user, pasw, token

def getSetting(token, action):
	"""
		Get action data/value for token.
	"""
	o = getData(token)
	if 'settings' not in o:
		o['settings'] = {'notif':{'disable': False, 'ignore':[]}}
	if action == 'notif.disable':
		return o['settings']['notif']['disable']
	if action == 'notif.ignore':
		return o['settings']['notif']['ignore']
	if action == 'notif.all':
		return o['settings']['notif']
	raise NonExistentSetting

def processSetting(token, action, val):
	"""
		Do an action, with val as the data/arguments on a profile.
	"""
	o = getData(token)
	if 'settings' not in o:
		o['settings'] = {'notif':{'disable': False, 'ignore':[]}}
	if action == 'notif.disable':
		o['settings']['notif']['disable'] = val
	elif action == 'notif.ignore.add':
		if val not in o['settings']['notif']['ignore']:
			o['settings']['notif']['ignore'].append(val)
	elif action == 'notif.ignore.del':
		if val in o['settings']['notif']['ignore']:
			del o['settings']['notif']['ignore'][o['settings']['notif']['ignore'].index(val)]
		else:
			raise NonExistentSetting
	else:
		raise NonExistentSetting
	saveData(token, o)

def purgeToken(token):
	"""
		Remove a token from the DB and terminate its sync thread.
	"""
	log.info("LOGOUT => %s", token)
	_stopSync(token)
	_redis.delete('token:' + token)
	rm_credentials(token)

def _formatAndSendNotification(token, notifData):
	"""
		Format a notification for the user based on data gotten from
		profileDifference() in sync().
	"""
	gradeNotif = []
	testNotif = []
	noteNotif = []
	absenceNotif = ""
	toSendQueue = []
	exceptions = getData(token)['settings']['notif']['ignore']
	for x in notifData:
		if x['type'] == 'test' and 'test' not in exceptions:
			testNotif.append("%s: %s" % (x['data']['subject'], x['data']['test']))
		elif x['type'] == 'grade' and 'grade' not in exceptions:
			gradeNotif.append("%s: %s (%s)" % (_getNameForSubjId(token, x['classId'], x['subjectId']), x['data']['grade'], x['data']['note']))
		elif x['type'] == 'note' and 'note' not in exceptions:
			noteNotif.append("%s: %s" % (_getNameForSubjId(token, x['classId'], x['subjectId']), x['data']['note']))
		elif x['type'] == 'absence' and 'absence' not in exceptions:
			absenceNotif = "ABS"
	if gradeNotif:
		toSendQueue.append({
			'head': localize(token, 'grade'),
			'content': ", ".join(gradeNotif)
		})
	if testNotif:
		toSendQueue.append({
			'head': localize(token, 'test'),
			'content': ", ".join(testNotif)
		})
	if noteNotif:
		toSendQueue.append({
			'head': localize(token, 'note'),
			'content': ", ".join(noteNotif)
		})
	if absenceNotif:
		toSendQueue.append({
			'head': localize(token, 'absence'),
			'content': absenceNotif
		})
	for i in toSendQueue:
		sendNotification(token, i['head'], i['content'])

def _getNameForSubjId(token, class_id, subject_id):
	"""
		Get the name belonging to a subject ID.
	"""
	if not verifyRequest(token, class_id, subject_id):
		raise Exception('Bad auth data')
	return getData(token)['data']['classes'][class_id]['subjects'][subject_id]['subject']

def _stopSync(token):
	"""
		Stop background sync thread for a given token, e.g. if
		terminated.
	"""
	if "sync:" + token in _threads:
		_threads["sync:" + token]["run"] = False

def getSyncThreads():
	"""
		Get a list of sync threads.
	"""
	return [i.replace("sync:", "") for i in _threads]

def isThreadAlive(token):
	"""
		Return the isAlive() of the sync thread belonging to a
		given token.
	"""
	return _threads["sync:" + token]["obj"].isAlive()

def startSync(token):
	"""
		Start a sync thread for a given token.
	"""
	global _threads
	if "sync:" + token not in _threads:
		to = Thread(target=_sync, args=(token,))
		to.start()
		_threads["sync:" + token] = {"obj":to, "run":True}

def restoreSyncs():
	"""
		Restore all sync threads (on startup).
	"""
	for token in getTokens():
		if not 'ignore_updating' in getData(token):
			startSync(token)

def syncDev(data2, token):
	"""
		DEV: Simulate sync with two objects.
	"""
	log.debug("Simulating sync")
	o = getData(token)
	diff = _profileDifference(o["data"], data2)
	if diff:
		log.debug("Difference detected")
		o["new"] = diff
		saveData(token, o)
		_formatAndSendNotification(token, diff)

def sync(token):
	"""
		Pull remote data, compare with current and replace if needed.
	"""
	log.debug("Syncing %s", token)
	fData = getData(token)
	data = fData["data"] # Old data
	credentials = get_credentials(token)
	nData = populateData(edap.edap(credentials["username"], credentials["password"])) # New data
	diff = _profileDifference(data, nData)
	if diff:
		# Overwrite everything if new class
		if diff[0]['type'] == 'class':
			fData["data"] = nData
		else:
			fData["data"][0] = nData[0]
		fData["new"] = diff
		saveData(token, fData)
		if not fData["settings"]["notif"]["disable"]:
			_formatAndSendNotification(token, diff)

def _profileDifference(dObj1, dObj2):
	"""
		Return the difference between two student data dicts.
	"""
	start = _clock()
	_finalReturn = []
	## CLASS DIFFERENCE ##
	t1 = deepcopy(dObj1['classes'])
	t2 = deepcopy(dObj2['classes'])
	for y in [t1, t2]:
		del y[0]['tests']
		del y[0]['subjects']
	difflist = [x for x in t2 if x not in t1]
	if difflist:
		log.debug("Found difference in classes")
		for i in difflist:
			_finalReturn.append({'type':'class', 'data':{'year':i["year"], 'class':i["class"]}})
		# At this point, we can't compare anything else, as only the
		# first class' information is pulled by populateData(), so
		# we'll just return.
		return _finalReturn
	## TEST DIFFERENCE (FIRST CLASS ONLY) ##
	t1 = deepcopy(dObj1['classes'][0]['tests'])
	t2 = deepcopy(dObj2['classes'][0]['tests'])
	difflist = [x for x in t2 if x not in t1]
	if difflist:
		log.debug("Found difference in tests")
		for i in difflist:
			_finalReturn.append({'type':'test', 'classId':0, 'data':i})
	## ABSENCE DIFFERENCE (FIRST CLASS ONLY) ##
	# Only check length to avoid spamming notifications for
	# each class period.
	t1 = deepcopy(dObj1['classes'][0]['absences']['full'])
	t2 = deepcopy(dObj2['classes'][0]['absences']['full'])
	if len(t1) != len(t2):
		log.info("Found difference in absences")
		_finalReturn.append({'type':'absence', 'classId':0, 'data':{'diff':len(t2)-len(t1)}})
	## PER-SUBJECT GRADE DIFFERENCE (FIRST CLASS ONLY) ##
	# https://stackoverflow.com/a/1663826
	sId = 0
	for i, j in zip(dObj1['classes'][0]['subjects'], dObj2['classes'][0]['subjects']):
		if "grades" in j:
			if j["grades"] is None:
				continue
			t1 = deepcopy(i['grades'])
			t2 = deepcopy(j['grades'])
			difflist = [x for x in t2 if x not in t1]
			if difflist:
				log.debug("Found difference in grades")
				for x in difflist:
					_finalReturn.append({'type':'grade', 'classId':0, 'subjectId': sId, 'data':x})
		elif "notes" in j:
			if j["notes"] is None:
				continue
			t1 = deepcopy(i['notes'])
			t2 = deepcopy(j['notes'])
			difflist = [x for x in t2 if x not in t1]
			if difflist:
				log.debug("Found difference in notes")
				for x in difflist:
					_finalReturn.append({'type':'note', 'classId':0, 'subjectId': sId, 'data':x})
		else:
			continue
		sId += 1
	request_time = _clock() - start
	log.debug("==> TIMER => {0:.0f}ms".format(request_time))
	return _finalReturn

def saveData(token, dataObj):
	"""
		Save data for a token.
	"""
	_redis.set('token:' + token, _jsonConvert(dataObj))

def getDBSize():
	"""
		Get the size of Redis' appendonly.aof database in bytes.
	"""
	return _getFileSize(_joinPath(config["DATA_FOLDER"], "appendonly.aof"))

def timeGenerated(startTime):
	"""
		Return a templated "Page generated in <time>" footer for dynamic
		/dev/ pages.
	"""
	return "<small>Page generated in %0.3f ms</small>" % ((_clock() - startTime)*1000.0)

def sendNotification(token, title, content, data=None):
	"""
		Send a notification to a user's device through Firebase.
	"""
	if not verifyRequest(token):
		raise Exception("Bad token")
	log.info("Sending notification to %s", token)
	firebaseToken = getData(token)["firebase_device_token"]

	try:
		_fbPushService.notify_single_device(registration_id=firebaseToken, message_title=title, message_body=content, data_message=data)
	except Exception as e:
		log.error('Unknown error (Firebase Cloud Messaging) => %s', str(e))
		raise e

def _sync(token):
	"""
		Wrapper around sync, for bg execution (random timeout).
	"""
	while True:
		val = randint(3600, 5000)
		log.debug("Waiting %i s for %s", val, token)
		sleep(val)
		if not _threads["sync:" + token]["run"]:
			del _threads["sync:" + token]
			break
		sync(token)

def _getVar(varname, _bool=False, default=None):
	"""
		Get environment variable and return it if it exists. If _bool is True,
		return it as a boolean value. If default is set, return its value if
		the given variable does not exist.
	"""
	if _bool:
		default = default if default != None else False
	try:
		return environ[varname] if not _bool else environ[varname] == "Y"
	except KeyError:
		return default

def _initGoogleToken(fpath):
	if not _fileExists(fpath):
		print("ERROR => File %s given to initGoogleToken() does not exist!" % fpath)
		_exit(1)
	environ["GOOGLE_APPLICATION_CREDENTIALS"] = fpath

def _readConfig():
	global _fbPushService
	DATA_FOLDER = _getVar("DATA_FOLDER", default="/data")
	GOOGLE_TOKEN_FILE = _getVar("GOOGLE_TOKEN_FILE", default="google_creds.json")

	VAULT_SERVER = _getVar("VAULT_SERVER")
	VAULT_TOKEN_READ = _getVar("VAULT_TOKEN_READ")
	VAULT_TOKEN_WRITE = _getVar("VAULT_TOKEN_WRITE")

	if not VAULT_TOKEN_READ or not VAULT_TOKEN_WRITE:
		print("[configuration] No Hashicorp Vault tokens supplied!")
		_exit(1)
	elif not VAULT_SERVER:
		print("[configuration] No Hashicorp Vault server supplied!")
		_exit(1)

	ALLOW_DEV_ACCESS = _getVar("DEV_ACCESS", _bool=True)
	USE_CLOUDFLARE = _getVar("CLOUDFLARE", _bool=True)
	USE_FIREBASE = _getVar("FIREBASE", _bool=True)

	privUsername = privPassword = None
	FIREBASE_TOKEN = None

	if ALLOW_DEV_ACCESS:
		privUsername = _getVar("DEV_USER")
		privPassword = _getVar("DEV_PASW")
		if not privUsername or not privPassword:
			print("[configuration] Dev access has been disabled, either no user or pass specified")
			privUsername = privPassword = None
			ALLOW_DEV_ACCESS = False

	if USE_FIREBASE:
		FIREBASE_TOKEN = _getVar("FIREBASE_TOKEN")
		_initGoogleToken(_joinPath(DATA_FOLDER, GOOGLE_TOKEN_FILE))
		if not FIREBASE_TOKEN:
			print("[configuration] Firebase has been disabled, no token specified")
			USE_FIREBASE = False
		else:
			print("[configuration] Initializing Firebase Cloud Messaging...")
			_fbPushService = FCMNotification(api_key=FIREBASE_TOKEN)
	return {
		"DATA_FOLDER": DATA_FOLDER,
		"GOOGLE_TOKEN_FILE": GOOGLE_TOKEN_FILE,
		"USE_CLOUDFLARE": USE_CLOUDFLARE,
		"ALLOW_DEV_ACCESS": ALLOW_DEV_ACCESS,
		"privUsername": privUsername,
		"privPassword": privPassword,
		"USE_FIREBASE": USE_FIREBASE,
		"FIREBASE_TOKEN": FIREBASE_TOKEN,
		"VAULT_SERVER": VAULT_SERVER,
		"VAULT_TOKEN_READ": VAULT_TOKEN_READ,
		"VAULT_TOKEN_WRITE": VAULT_TOKEN_WRITE
	}

def readLog():
	with open(_joinPath(config["DATA_FOLDER"], "edap_api.log")) as f:
		return f.read()

def makeHTML(title="eDAP dev", content=None, bare=False):
	"""
		HTML creator template for the /dev/ dashboard. Allows specifying the title,
		content, and if the page needs to have no header (e.g. the /dev/log page).
	"""
	if not bare:
		return '<!DOCTYPE html><html><head><title>%s</title></head><body><h1>%s</h1>%s</body></html>' % (title, title, content)
	else:
		return '<!DOCTYPE html><html><head><title>%s</title></head><body>%s</body></html>' % (title, content)

# https://stackoverflow.com/a/14822210
def convertSize(size_bytes):
	"""
		Convert bytes to a human-readable format.
	"""
	if size_bytes == 0:
		return "0B"
	size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
	i = int(_mFloor(_mLog(size_bytes, 1024)))
	p = _mPow(1024, i)
	s = round(size_bytes / p, 2)
	return "%s %s" % (s, size_name[i])

def _initDB(host="localhost", port=6379, db=0):
	"""
		Initialize the Redis DB.
	"""
	try:
		r = redis.Redis(host=host, port=port, db=db)
		if r.ping():
			log.info("Database connection successful")
			return r
		else:
			log.critical("Database connection failed!")
			_exit(1)
	except redis.exceptions.ConnectionError:
		log.critical("Database connection failed!")
		_exit(1)

def getData(token):
	"""
		Retreive JSON from Redis by token, format it from bytes to string,
		and return it as a dict.
	"""
	return _jsonLoad(_redis.get("token:" + token).decode("utf-8"))

def getTokens():
	"""
		Return a list of all tokens in the DB.
	"""
	return [i.decode('utf-8').replace("token:", "") for i in _redis.keys('token:*')]

def _userInDatabase(token):
	"""
		Check if a given token exists in the DB.
	"""
	return "token:" + token in [i.decode('utf-8') for i in _redis.keys('token:*')]

def _classIDExists(token, cid):
	"""
		Check if a given class ID exists in the DB. Assumes that userInDatabase()
		was already called and returned True.
	"""
	return cid <= len(getData(token)['data']['classes'])

def _subjectIDExists(token, cid, sid):
	"""
		Check if a given subject ID exists in the DB. Assumes that userInDatabase()
		and classIDExists() were both already called and returned True.
	"""
	return sid in range(len(getData(token)['data']['classes'][cid]['subjects']))

def fetch_new_class(token, class_id):
	"""
		Fetch a new class
	"""
	full_data = getData(token)
	# If not already pulled
	if not 'full' in full_data['data']['classes'][class_id]:
		credentials = get_credentials(token)
		edap_object = edap.edap(credentials['username'], credentials['password'])
		# Get the classes so they're saved in the object
		edap_object.getClasses()
		# Overwrite existing "bare" class profile with new complete profile
		full_data['data']['classes'][class_id] = get_class_profile(
			edap_object,
			class_id,
			full_data['data']['classes'][class_id]
		)
		saveData(token, full_data)

def populateData(obj):
	"""
		Fill in the 'data' part of the user dict. This will contain subjects, grades, etc.

		First, get the class list (this also fills the class ID list for eDAP).

		Second, get the list of tests for the first class, both current and full, and
		compare them, assigning a "current" flag to each which will say if the test
		has already been written or not.

		Third, get the subjects for a class, and get the grades for each one. If there
		is a concluded grade available, use it as the average, otherwise calculate an average.
		Get the list of "additional notes" for each subject.

		Fourth, write this data into the "classes" key in the dict.

		Fifth, get the user's personal info and write it into the "info" key in the dict.

		Finally, return all the collected data.
	"""
	data_dict = {'classes':None}
	try:
		output = obj.getClasses()
	except Exception as e:
		log.error("Error getting classes: %s", e)
		raise e

	output[0] = get_class_profile(obj, 0, output[0])
	data_dict['classes'] = output
	return data_dict

def get_class_profile(obj, class_id, class_obj):
	try:
		tests_nowonly = obj.getTests(class_id, alltests=False)
		tests_all = obj.getTests(class_id, alltests=True)
		testId = 0
		for x in tests_all:
			if x not in tests_nowonly:
				x['current'] = False
			else:
				x['current'] = True
			x['id'] = testId
			testId += 1
		class_obj['tests'] = tests_all
	except Exception as e:
		log.error("Error getting tests for class: %s", e)
		class_obj['tests'] = None

	try:
		absences_overview = obj.getAbsentOverviewForClass(class_id)
		class_obj['absences'] = {'overview':absences_overview, 'full':None}
	except Exception as e:
		log.error("Error getting absence overview for class: %s", e)
		class_obj['absences'] = None
	try:
		if class_obj['absences'] != None:
			absences_full = obj.getAbsentFullListForClass(class_id)
			class_obj['absences']['full'] = absences_full
	except Exception as e:
		log.error("Error getting absence full list for class: %s", e)

	try:
		class_obj['subjects'] = obj.getSubjects(class_id)
	except Exception as e:
		log.error("Error getting subjects for class: %s", e)
		class_obj['subjects'] = None
	allSubjAverageGrades = []
	for z in range(len(class_obj['subjects'])):
		class_obj['subjects'][z]['id'] = z
		try:
			class_obj['subjects'][z]['grades'] = obj.getGradesForSubject(class_id, z)
			if not class_obj['subjects'][z]['grades']:
				class_obj['subjects'][z]['grades'] = None
			isconcl, concluded = obj.getConcludedGradeForSubject(0, z)
			if isconcl:
				class_obj['subjects'][z]['average'] = concluded
				allSubjAverageGrades.append(concluded)
			else:
				lgrades = []
				for i in class_obj['subjects'][z]['grades']:
					lgrades.append(i['grade'])
				class_obj['subjects'][z]['average'] = round(sum(lgrades)/len(lgrades), 2)
				allSubjAverageGrades.append(round(sum(lgrades)/len(lgrades), 0))
		except Exception as e:
			log.error("Error getting grades for subject %s: %s", z, e)
			class_obj['subjects'][z]['grades'] = None
			continue
		try:
			class_obj['subjects'][z]['notes'] = obj.getNotesForSubject(class_id, z)
			if not class_obj['subjects'][z]['notes']:
				class_obj['subjects'][z]['notes'] = None
		except Exception as e:
			log.error("Error getting notes for subject %s: %s", z, e)
			class_obj['subjects'][z]['notes'] = None
			continue
	try:
		class_obj['complete_avg'] = round(sum(allSubjAverageGrades)/len(allSubjAverageGrades), 2)
	except:
		class_obj['complete_avg'] = 0
	try:
		class_obj['info'] = obj.getInfoForUser(0)
	except Exception as e:
		log.error("Error getting info: %s", str(e))
	class_obj['full'] = True
	return class_obj

def verifyDevRequest(token):
	"""
		Verify if a given dev API token is valid.
	"""
	return "dev-token:" + token in [i.decode('utf-8') for i in _redis.keys('dev-token:*')]

def addDevToken():
	"""
		Authorizes a dev API token.
	"""
	token = hashPassword(random_string(28))
	_redis.set('dev-token:' + token, 'ALLOWED')
	return token

def verifyRequest(token, class_id=None, subject_id=None):
	"""
		Verify if a given token, class_id, and/or subject_id exist in the DB.
	"""
	if not _userInDatabase(token):
		log.warning("Token %s not in DB", token)
		return False
	if class_id:
		if not _classIDExists(token, class_id):
			log.warning("Class ID %s does not exist for token %s", class_id, token)
			return False
	if subject_id:
		if not _subjectIDExists(token, class_id, subject_id):
			log.warning("Subject ID %s does not exist for class ID %s for token %s", subject_id, class_id, token)
			return False
	return True

def hashString(inp):
	"""
		Return the MD5 hash of a string. Used for tokens.
	"""
	return _MD5HASH(inp.encode()).hexdigest()

def hashPassword(inp):
	"""
		Return the SHA256 hash of a string. Used for the /dev/ password.
	"""
	return _SHA256HASH(inp.encode()).hexdigest()

def getCounter(counter_id):
	val = _redis.get("counter:"+counter_id)
	if val is None:
		_redis.set("counter:"+counter_id, 0)
		return 0
	return int(val)

def _setCounter(counter_id, value):
	_redis.set("counter:"+counter_id, value)

def updateCounter(counter_id):
	val = getCounter(counter_id)
	_setCounter(counter_id, val+1)

config = _readConfig()
logging.basicConfig(
	filename=_joinPath(config["DATA_FOLDER"], "edap_api.log"),
	level=logging.INFO,
	format="%(asctime)s || %(funcName)-16s || %(levelname)-8s || %(message)s"
)
_redis = _initDB()
