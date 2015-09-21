angular.module('app', [
  // external libs
  'ngRoute',
  'ngResource',
  'ui.bootstrap',
  'ngProgress',
  'ngSanitize',

  'templates.app',  // this is how it accesses the cached templates in ti.js

  'staticPages',
  'personPage',
  'articlePage',
  'header',
  'packageSnippet',

  'resourcesModule',
  'pageService',

  'top'

]);




angular.module('app').config(function ($routeProvider,
                                       $locationProvider) {
  $locationProvider.html5Mode(true);


//  paginationTemplateProvider.setPath('directives/pagination.tpl.html')
});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   ngProgress,
                                   $location) {



  $rootScope.$on('$routeChangeStart', function(next, current){
    console.log("route change start")
    ngProgress.start()
  })
  $rootScope.$on('$routeChangeSuccess', function(next, current){
    console.log("route change success")
    ngProgress.complete()
  })
  $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
    console.log("$routeChangeError")
    ngProgress.complete()
  });


  // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
  (function(o) {
    Number.getOrdinalFor = function(intNum, includeNumber) {
      return (includeNumber ? intNum : "")
        + (o[((intNum = Math.abs(intNum % 100)) - 20) % 10] || o[intNum] || "th");
    };
  })([,"st","nd","rd"]);



  /*
  this lets you change the args of the URL without reloading the whole view. from
     - https://github.com/angular/angular.js/issues/1699#issuecomment-59283973
     - http://joelsaupe.com/programming/angularjs-change-path-without-reloading/
     - https://github.com/angular/angular.js/issues/1699#issuecomment-60532290
  */
  var original = $location.path;
  $location.path = function (path, reload) {
      if (reload === false) {
          var lastRoute = $route.current;
          var un = $rootScope.$on('$locationChangeSuccess', function () {
              $route.current = lastRoute;
              un();
          });
        $timeout(un, 500)
      }
      return original.apply($location, [path]);
  };




});


angular.module('app').controller('AppCtrl', function(
  $rootScope,
  $scope,
  $location,
  $sce,
  PageService){



  $scope.page = PageService

  $scope.nFormatter = function(num){
      // from http://stackoverflow.com/a/14994860/226013
      if (num === null){
        return 0
      }

      if (num >= 1000000) {
          return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
      }
      if (num >= 1000) {
          return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
      }

      if (num < .01) {
        return num.toExponential(1)
      }
      if (num < 1) {
        return Math.round(num * 100) / 100
      }

      return Math.floor(num);
  }


  function toRoundedSciNotation(n){

  }

  // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
  $scope.getOrdinal = function(n) {
    var s=["th","st","nd","rd"],
      v=n%100;
    return n+(s[(v-20)%10]||s[v]||s[0]);
  }

  $scope.toPercentile = function(proportion){
    return $scope.getOrdinal(Math.floor(proportion * 100))
  }

  $scope.floor = function(num){
    return Math.floor(num)
  }


  $scope.trustHtml = function(str){
    console.log("trusting html:", str)
    return $sce.trustAsHtml(str)
  }



  /*
  $scope.$on('$routeChangeError', function(event, current, previous, rejection){
    RouteChangeErrorHandler.handle(event, current, previous, rejection)
  });
  */


  $scope.$on('$locationChangeStart', function(event, next, current){
  })


});

