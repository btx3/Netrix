import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { Storage } from '@ionic/storage';
import { Platform } from '@ionic/angular';
import { HttpClient } from '@angular/common/http';
import { map, catchError, switchAll } from 'rxjs/operators';
import { Observable, throwError } from 'rxjs';
import { Device } from '@ionic-native/device/ngx';

@Injectable({
	providedIn: 'root'
})
export class AuthenticationService {

	authenticationState = new BehaviorSubject(false);
	token = null;
	dataPreference = null;
	notifPreference = null;
	API_SERVER = "https://api.netrix.io";

	constructor(private storage: Storage, private plt: Platform, private http: HttpClient, private device: Device) {
		this.plt.ready().then(() => {
			console.log("AuthenticationService: API server is " + this.API_SERVER)
			this.checkToken()
		})
	}

	changePreference(pref, prefValue) {
		this.storage.set(pref, prefValue).then(() => {
			console.log("AuthenticationService/changePreference(): Set " + pref + " to " + prefValue);
		})
	}

	checkToken() {
		this.storage.get("auth-token").then(res => {
			if (res) {
				this.token = res;
				console.log("AuthenticationService/checkToken(): Found saved token (" + this.token + ")");
				this.storage.get("data-preference").then(res => {
					this.dataPreference = res;
					console.log("AuthenticationService/checkToken(): Found analytics preference (" + this.dataPreference + ")");
				})
				this.authenticationState.next(true);
			}
		})
	}

	login(username, password) {
		let response:Observable<Response> = this.http.post<Response>(this.API_SERVER + "/api/login", {"username":username, "password":password, "platform":this.device.platform, "device":this.device.model});

		let jsonResponse = response.pipe(catchError(err => this.handleError(err)));

		let userResponse = jsonResponse.pipe(map(
			data => this.handleLogin(data)
		));

		return userResponse;
	}

	private handleLogin(data) {
		this.storage.set("auth-token", data.token).then(() => {
			this.token = data.token;
			console.log("AuthenticationService/handleLogin(): Login successful, got token (" + data.token + ")");
			this.storage.set("data-preference", true).then(() => {
				console.log("AuthenticationService/handleLogin(): Analytics preference defaulted to true")
			})
			this.authenticationState.next(true);
		})
	}

	private handleError(error) {
		return throwError(error);
	}

	logout() {
		return this.storage.remove("auth-token").then(() => {
			this.authenticationState.next(false);
		})
	}

	isAuthenticated() {
		return this.authenticationState.value;
	}
}
