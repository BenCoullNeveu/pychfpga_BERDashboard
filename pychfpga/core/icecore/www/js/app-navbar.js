iceboardApp.controller('navbarController', function($q, $http, $scope) {
	TuberObject($q, $http, 'IceBoard')
	.then(function(ib) {
		$scope.ib = ib
		ib._get_personality()
		.then(function(p) {
			$scope.personality = p
		})
		ib.flush()
	});
});

/* vim: set ts=4 sw=4: */
