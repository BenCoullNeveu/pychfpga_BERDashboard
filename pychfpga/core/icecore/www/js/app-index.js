iceboardApp.controller('indexController', function($q, $scope, ib) {
	ib._get_motherboard_ipmi().then(function(x) { $scope.serial_number = x['board']['serial_number'] })
	ib._get_personality().then(function(x) { $scope.personality = x });
	ib.flush()
});

/* vim: set ts=4 sw=4: */
