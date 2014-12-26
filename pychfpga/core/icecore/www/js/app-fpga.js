iceboardApp.controller('fpgaController', function($q, $scope, ib) {

	/* Embed IceBoard so we can interact with it. */
	$scope.ib = ib;

	/* FPGA information */
	ib.is_fpga_programmed().then(function(x) { $scope.is_fpga_programmed = x })

	ib.flush()
});

/* vim: set ts=4 sw=4: */
