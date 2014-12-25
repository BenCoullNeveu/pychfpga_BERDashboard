var iceboardApp = angular.module('iceboardApp', ['ngRoute']);
ib_resolver = { ib: [ "$q", "$http", function($q, $http) { return TuberObject($q, $http, 'IceBoard') } ] }

iceboardApp.config(function($routeProvider, $locationProvider) {
	$routeProvider
	.when('/', {
		templateUrl	: 'views/index.html',
		controller	: 'indexController',
		resolve		: ib_resolver
	})
	.when('/status/housekeeping', {
		templateUrl : 'views/housekeeping.html',
		controller  : 'housekeepingController',
		resolve     : ib_resolver,
	})
	.when('/status/ipmi', {
		templateUrl : 'views/ipmi.html',
		controller  : 'versionsController',
		resolve     : ib_resolver,
	})
	.when('/status/log', {
		templateUrl : 'views/log.html',
		controller  : 'logController',
		resolve     : ib_resolver,
	})
	.when('/status/fpga', {
		templateUrl : 'views/fpga.html',
		controller  : 'fpgaController',
		resolve     : ib_resolver,
	})
	.when('/status/mezzanines', {
		templateUrl : 'views/mezzanines.html',
		controller  : 'mezzaninesController',
		resolve     : ib_resolver,
	})

	.when('/documentation/links', { templateUrl : 'views/links.html' })
	.when('/documentation/contacts', { templateUrl : 'views/contacts.html' })
	.when('/documentation/design', { templateUrl : 'views/design.html' })
	.otherwise({ redirectTo: '/' });
});

/* vim: set ts=4 sw=4: */
