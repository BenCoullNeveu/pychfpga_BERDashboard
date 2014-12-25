iceboardApp.controller('logController', function($q, $scope, ib) {
	ib._get_syslog_buffer().then(function(x) { $scope.log_data = x })
	ib.flush()
});

/* vim: set ts=4 sw=4: */
