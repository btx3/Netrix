import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthenticationService } from '../authentication.service'
import { TranslateService } from '@ngx-translate/core';
import { ToastController } from '@ionic/angular';
import { trigger, state, style, animate, transition } from "@angular/animations";
import { timeout } from 'rxjs/operators';

@Component({
  selector: 'app-tab4',
  templateUrl: 'tab4.page.html',
  styleUrls: ['tab4.page.scss'],
  animations: [
    trigger('animChange', [
      state('opaque', style({ opacity: 1 })),
      state('transparent', style({ opacity: 0 })),
      transition('transparent => opaque', animate('500ms ease-out'))
    ])
  ]
})
export class Tab4Page {

  student = {"name":null, "birthdate":null, "address":null};
  titleState = "transparent";

  constructor(private translate: TranslateService, private toastCtrl: ToastController, private http: HttpClient, private authServ: AuthenticationService) {
    this.collectStudentData();
  }

  toastError(msg, btns, dur) {
    this.toastCtrl.create({
      message: msg,
      buttons: btns,
      color: 'dark',
      duration: dur
    }).then((toast) => {
      toast.present();
    });
  }

  async collectStudentData() {
    this.http.get<any>(this.authServ.API_SERVER + '/api/user/' + this.authServ.token + '/info').pipe(timeout(3000)).subscribe((response) => {
      this.student = response;
      console.log("tab4/collectStudentData(): Got user info successfully");
      this.titleState = "opaque";
    }, (error) => {
      if (error.error.error === "E_TOKEN_NONEXISTENT") {
        // User is not authenticated (possibly token purged from server DB)
        this.toastError(this.translate.instant("generic.alert.expiry"), null, 2500);
        this.authServ.logout();
      } else if (error.error.error === "E_DATABASE_CONNECTION_FAILED") {
        // Server-side issue
        this.toastError(this.translate.instant("generic.alert.database"), null, 2500);
        throw new Error('Database connection failed');
      } else {
        // No network on client
        //this.networkError(this.translate.instant("generic.alert.network.header"), this.translate.instant("generic.alert.network.content"));
        this.toastError(this.translate.instant("generic.alert.network"), [{text: 'Reload', handler: () => {this.collectStudentData()}}], null)
        throw new Error('[collectStudentData()] Network error');
      }
    })
  }

}
