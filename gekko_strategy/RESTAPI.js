/**
 * Author: Marius Helf
 *
 * RESTAPI strategy to be used in combination with GekkoPy:
 * https://github.com/mariushelf/gekkopy
 */
const request = require('sync-request');
const log = require('../core/log.js');

// Let's create our own strategy
const strategy = {};

const makeAdviceLog = (type, price) => {
  log.debug(`${type} at ${price}`);
  console.log(`${type} at ${price}`);
};

// Prepare everything our strategy needs
strategy.init = function() {
  log.debug('settings', this.settings);
  const {
    url,
  } = this.settings;
  this.url = url;

  // init window size
  var res = request('GET', url + '/window_size');
  this.windowSize = JSON.parse(res.body)['window_size'];
  this.requiredHistory = this.windowSize;

  this.data = [];
  this.currentAdvice = null;
  this.count = 0;
};


// What happens on every new candle?
strategy.update = function(candle) {
  this.count += 1;
  this.data.push([
    candle.open, candle.high, candle.low,
    candle.close, candle.volume, candle.trades,
  ]);
  if (this.data.length > this.windowSize) {
    this.data.shift();
  }
  console.log(this.count, this.data.length);
  if (this.data.length >= this.windowSize) {
    res = request('POST', this.url + '/advice', {
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(this.data),
    });
    console.log(JSON.parse(res.body));
    this.currentAdvice = JSON.parse(res.body)['advice'];
  }
};

// For debugging purposes.
strategy.log = function() {

};

// Based on the newly calculated
// information, check if we should
// update or not.
strategy.check = function(candle) {
  this.advice(this.currentAdvice);
};

// Optional for executing code
// after completion of a backtest.
// This block will not execute in
// live use as a live gekko is
// never ending.
strategy.end = function() {

};

module.exports = strategy;
