iceboardApp.controller('housekeepingController', function($q, $scope, $interval, ib) {

	$scope.ib = ib

	/* Initialize scope variables */
	$scope.motherboard_rails = {}
	$scope.motherboard_temperatures = {}
	$scope.mezzanine_rails = { 1: {}, 2: {} }

	for(var i in ib.RAIL) {
		var sensor = ib.RAIL[i]
		if(sensor.match('MOTHERBOARD'))
			$scope.motherboard_rails[sensor] = {}
		if(sensor.match('MEZZANINE')) {
			$scope.mezzanine_rails[1][sensor] = {}
			$scope.mezzanine_rails[2][sensor] = {}
		}
	}

	$scope.num_motherboard_rails = Object.keys($scope.motherboard_rails).length
	$scope.num_mezzanine_rails = Object.keys($scope.mezzanine_rails[1]).length

	refresh = function() {
		/* Motherboard temperature sensors */
		for(var i in ib.TEMPERATURE_SENSOR) {
			(function(sensor){
				ib.get_motherboard_temperature(sensor).then(function(x) {
					$scope.motherboard_temperatures[sensor] = x
				})
			})(ib.TEMPERATURE_SENSOR[i])
		}

		/* Motherboard and mezzanine voltage sensors */
		for(var i in ib.RAIL) {
			(function(sensor) {
				if(sensor.match('MOTHERBOARD')) {
					ib.get_motherboard_voltage(sensor).then(function(x) {
						$scope.motherboard_rails[sensor].voltage = x
					});
					ib.get_motherboard_current(sensor).then(function(x) {
						$scope.motherboard_rails[sensor].current = x
					});
				}

				if(sensor.match('MEZZANINE')) {
					for(var i=1; i<=ib.NUM_MEZZANINES; i++) {
						(function(mezzanine) {
							ib.get_mezzanine_voltage(sensor, i).then(function(x) {
								$scope.mezzanine_rails[mezzanine][sensor].voltage = x
							});
							ib.get_mezzanine_current(sensor, i).then(function(x) {
								$scope.mezzanine_rails[mezzanine][sensor].current = x
							});
						})(i);
					}
				}
			})(ib.RAIL[i]);
		}

		ib.flush()
	}

	var timer = $interval(refresh, 5000)
	$scope.$on("$destroy", function(event) { $interval.cancel(timer) })
	refresh()
});

/* vim: set ts=4 sw=4: */
