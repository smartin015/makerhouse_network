const express = require('express');
const request = require('request');
const app = express();
const config = require('./config');

if (config.SHEET_KEY === 'YOUR_SHEET_KEY_HERE') {
  throw new Error("You must first change the sheet key in config.js before starting.");
}

// Map shorturl path to actual URL
var urlmap = {};

function fetch_url_sheet(uri) {
  request('https://docs.google.com/spreadsheets/d/e/' + config.SHEET_KEY + '/pub?gid=0&single=true&output=csv', (err, resp, body) => {
    if( err !== null) {
      console.error(err);
      return;
    } else if (resp.statusCode !== 200) {
      console.error("GET response " + resp.statusCode);
      return;
    }
    let newmap = {}
    for (let line of body.split("\n")) {
      let csv = line.split(",");
      if (!csv[1].startsWith("http")) {
        continue; // Likely the header
      } 
      newmap[csv[0]] = csv[1];
    }
    urlmap = newmap;
    console.log("URL map updated (" + Object.keys(urlmap).length + " items)");
  });
}

const setupRoutes = function(app) {
  const router = express.Router();
  router.get('/_forcereload', (req, res) => {
  	fetch_url_sheet();
  	res.send('Reloaded - updates should be visible in a few seconds.');
  	res.status(200).end();
  })
  router.get('/:shorturl', (req, res) => {
 		var true_url = urlmap[req.params.shorturl];
	 	if (!true_url) {
	 		res.status(404).end();
      console.log("404 NOTFOUND " + req.params.shorturl);
	 		return;
	 	}
    res.header('Location', true_url);
    console.log("301 OK/REDIRECT " + req.params.shorturl);
    res.status(301).end();
  });
  app.use(router);
};

if (module === require.main) {
	fetch_url_sheet();
	setInterval(fetch_url_sheet, config.REFRESH_INTERVAL);
  setupRoutes(app);
	const port = process.env.DOCKER_PORT || 8000;
  var server = app.listen(port, function () {
    var port = server.address().port;
    console.log('App listening on port %s', port);
  });
}

module.exports = app;
