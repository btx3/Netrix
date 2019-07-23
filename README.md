# Netrix (eDnevnik for Android)
![CircleCI](https://img.shields.io/circleci/build/github/btx3/Netrix.svg?label=build%3ANetrix&token=3f60d33e9cd7618f9b9af8b7c5e731baefb7934f)

* Backend - [eDAP](https://github.com/btx3/eDnevnik/blob/master/README_edap.md) (eDnevnikAndroidProject) [Python]
* Frontend - [Netrix](https://github.com/btx3/eDnevnik/blob/master/README_Netrix.md) [JS/Ionic]

![Banner za Netrix](https://i.imgur.com/VkQ7SQX.jpg)

## Buildovi/APKovi

Buildovi (.apk) su dostupni na [Releases](https://github.com/btx3/Netrix/releases) stranici.

Molimo pazite kako se projekt još uvijek razvija, pa stoga nemojte očekivati iskustvo bez grešaka.

Ako je moguće, nemojte koristiti master branch za build, već koristite unaprijed testirane i provjerene verzije preuzimanjem sa [Releases](https://github.com/btx3/Netrix/releases) stranice ili pomoću [`git checkout`](https://stackoverflow.com/a/792027) komande.

Svaku nađenu grešku je poželjno [prijaviti](https://github.com/btx3/Netrix/issues/new) (ako je moguće uz logove, screenshote itd.).

## Kako funkcionira

```
            ------------                 ----------------
           |  Frontend  |               |      API       |     --------              ----------
 - User -> | (JS/Ionic) | - ReST API -> | (Flask/Python) | -> |  eDAP  | - HTTPS -> | eDnevnik |
            ------------                |    TCP/5000    |     --------              ----------
                                         ----------------  
```

## Instalacija
Projekt je trenutno u fazi razvijanja, pa stoga nema jednostavnih skripta za postavljanje.

Upute za instalaciju možete pronaći na linkovima za backend i frontend gore.
