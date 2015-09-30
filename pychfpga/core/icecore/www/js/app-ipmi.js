iceboardApp.controller('versionsController', function($q, $scope, ib) {

	$scope.ipmi_blocks = {}

	/* Motherboard information */
	ib._get_motherboard_ipmi().then(function(x) { $scope.ipmi_blocks['Motherboard'] = x })
	ib._get_mezzanine_ipmi(1).then(function(x) { $scope.ipmi_blocks['Mezzanine 1'] = x })
	ib._get_mezzanine_ipmi(2).then(function(x) { $scope.ipmi_blocks['Mezzanine 2'] = x })

	ib.flush()
});

/* vim: set ts=4 sw=4: */
