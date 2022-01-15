# URL Shortener

This is a simple URL shortener that reads from a google spreadsheet.

## Setup

First export your sheet so it is readable by [Tabletop](https://www.npmjs.com/package/tabletop). You'll need two 
of the columns named `ShortURL segment` and `Target URL`.

Then add the pubhtml link to config.js under `SHEET_KEY`.

Run `npm install` to install dependencies, then `npm index.js` to start the resolution server.

## Usage

Add URLs as needed - if you want the change to take effect immediately, go to `http://your-hostname:<port>/_forcereload` and it'll automatically re-parse the spreadsheet.