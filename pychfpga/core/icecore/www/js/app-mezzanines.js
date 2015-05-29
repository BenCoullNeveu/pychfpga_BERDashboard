iceboardApp.controller('mezzaninesController', function($q, $scope, ib) {

	/* Embed IceBoard so we can interact with it. */
	$scope.ib = ib;

	/* FPGA information */
	ib.is_mezzanine_present(1).then(function(x) { $scope.m1_present = x })
	ib.get_mezzanine_power(1).then(function(x) { $scope.m1_powered = x })

	ib.is_mezzanine_present(2).then(function(x) { $scope.m2_present = x })
	ib.get_mezzanine_power(2).then(function(x) { $scope.m2_powered = x })

	ib.flush()
});

/* vim: set ts=4 sw=4: */
