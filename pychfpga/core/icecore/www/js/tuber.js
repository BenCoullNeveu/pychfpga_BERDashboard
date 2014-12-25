/*
 * TuberObject JavaScript interface.
 *
 * Interactions with a TuberObject look something like this:
 *
 *		x = TuberObject("Dfmux").done(function(dfmux) {
 *			dfmux.get_mezz_power(1).done(function(x) { console.log(x); });
 *			dfmux.get_mezz_power(2).done(function(x) { console.log(x); });
 *			dfmux.flush()
 *		});
 *
 * It's a little wordy, but this does absolutely everything we want it
 * to:
 *
 *		- constructing a TuberObject takes two requests (one for the object
 *			description, and one for all properties); these are cached, so
 *			the overhead is acceptable even if a TuberObject is extensively
 *			referenced. (This is not crazy, considering these requests are
 *			pretty small compared to JQuery or a small image.)
 *
 *    - multiple calls are aggregated into single array-style calls,
 *			and results are automatically propogated back in an easy-to-use
 *			idiom.
 */

var __TuberObjectCache = {};

function TuberObject($q, $http, objname) {
	/* We want to encourage proper encapsulation of TuberObject calls,
	 * so we cache objects aggressively. */

	if(objname in __TuberObjectCache)
		return __TuberObjectCache[objname];

	/* This Deferred is for the TuberObject call. It's triggered when
	 * the TuberObject is populated with methods and properties. */
	var dfd = $q.defer()

	var obj = Object({
		/* This Object is the Dfmux we attach properties and methods to.  Even
		 * though we make one function call at a time, we're actually only
		 * queueing them up; they aren't actually issued until we call flush()
		 * (below), when they're issued in a single command stream.
		 * TODO: error handling could probably be stricter. */

		flush: (function() {

			/* Claim calls */
			var calls = this.__calls
			var deferreds = this.__deferreds
			delete this.__calls
			delete this.__deferreds

			/* Shortcut without network interactions if there's nothing queued.
			 * This allows us to produce excess flush() calls without penalty. */
			if(!calls) {
				var dfd = $q.defer()
				dfd.resolve(null)
				return(dfd.promise)
			}

			/* Return the $http value, since it's a promise. Grab a reference
			 * to "deferreds", since it'll otherwise change behind our backs. */
			return (function(d) {
				return $http({
					method: 'POST',
					url: '/tuber',
					data: calls,
				}).success(function(data) {
					/* Sort through results, firing Deferreds as we go. */
					for(var i in data) {
						if('error' in data[i] && data[i].error)
							d[i].reject(data[i].error);
						else
							d[i].resolve(data[i].result);
					}
				});
			})(deferreds);
		}),
	});

	/* Load and cache properties, methods */
	$http({
		method: 'POST',
		url: '/tuber',
		data: {"object": objname}
	}).success(function(data) {

		/* This function is used to sidestep closure scoping issues;
		 * it's tempting to move it in-line, but we run into the
		 * following gotcha:
		 *
		 *     http://stackoverflow.com/questions/750486
		 */
		function __callbuilder(method) {
			/* This is the function you're looking for (for example,
			 * d.get_mezz_power(1) calls this directly.)
			 * All we do, here, is store the arguments and return a
			 * promise to call them in the future. The actual call is
			 * done by the flush() command (above) so that we can
			 * aggregate many calls. */
			return(function() {
				var dfd = $q.defer()

				var args = []
				for(var j in arguments)
					args.push(arguments[j])

				this.__calls = this.__calls || new Array()
				this.__deferreds = this.__deferreds || new Array()

				this.__calls.push({
					object: objname,
					method: method,
					args: args
				});
				this.__deferreds.push(dfd);
				return dfd.promise;
			});
		}

		/* For methods, create and attach a function object. */
		for(var i in data.result.methods) {
			var method = data.result.methods[i]
			Object.defineProperty(obj, method, {
				configurable: true,
				value: __callbuilder(method)
			});
		}

		/* We may as well retrieve all properties up-front, since there
		 * aren't likely to be that many of them (and one biggish array
		 * request is better than a handful of single-property requests.) */
		var prop_req = [];
		for(var i in data.result.properties) {
			prop_req.push({
				"object": objname,
				"property": data.result.properties[i],
			});
		}
		$http({
			method: 'POST',
			url: '/tuber',
			data: prop_req,
		}).success(function(data) {
			for(var i in prop_req) {
				Object.defineProperty(obj, prop_req[i].property, {
					value: data[i].result
				});
			}
			dfd.resolve(obj);
		});

	});

	__TuberObjectCache[objname] = dfd.promise
	return TuberObject($q, $http, objname);
}

<!-- vim: set ts=4 sw=4: -->
