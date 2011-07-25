/**
 *
 * copyright © 2010 ojuba.org, Muayyad Saleh Alsadi
 *
 **/
var klass="class";
var animations={}, ani_c=0, init_ls=[];
var autoscroll_dir=0, autoscroll_px=5;
var overlay_d;

// fake trim for IE
if (!Boolean(String.prototype.trim)) {
	String.prototype.trim = function() {
		return this.replace(/^\s+/, '').replace(/\s+$/, '');
	};
}

function get_url_vars() {
	var vars = {}, i,j, e;
	var s= document.location.search;
	if (!s || s.length[0]==0 || s[0]!="?" ) return vars;
	var a = s.slice(1).split('&');
	for(i = 0; i < a.length; ++i) {
		e = a[i].split("=",2);
		if (e && e.length==2) vars[decodeURI(e[0])] = decodeURI(e[1]);
	}
	return vars;
}

function animation_loop() {
	var i,a,fn,r;
	for (i in animations) {
		a=animations[i];
		fn=a[0];
		r=fn(a.slice(1));
		if (r==false) delete animations[i];
	}
	setTimeout(animation_loop, 100);
}

function slide_down_cb(args) {
	var o=args[0], h=args[1], px=args[2], cb=args[3];
	var t=o.offsetHeight+px;
	if (t>=h) t=h;
	o.style.height=t+"px";
	if (t==h) {
		--ani_c;
		if (cb) cb();
		return false;
	}
	return true
}

function slide_down(o, h, px, cb) {
	var d;
	if (!h || h<0) h=o.offsetHeight;
	if (!px || px<0) px=h/5.0;
	if (px<1.0) px=1;
	d=o.style.display;
	o.style.display="none";
	o.style.height=px+"px";
	o.style.display=d;
	animations["_"+(++ani_c)]=[slide_down_cb, o, h, px, cb];
}

function get_scroll_width() {
	var w = window.pageXOffset || document.body.scrollLeft || document.documentElement.scrollLeft;
	return w ? w : 0;
}

function get_scroll_height() {
	var h = window.pageYOffset || document.body.scrollTop || document.documentElement.scrollTop;
	return h ? h : 0;
}

function autoscroll_up_cb() {
	
	if (autoscroll_dir!=-1) return true;
	var h=get_scroll_height(),t=h-autoscroll_px;
	if (t<=0) {t=0; autoscroll_dir=0;}
	window.scroll(0,t);
	return true
}
function autoscroll_down_cb() {
	if (autoscroll_dir!=1) return true;
	var h=get_scroll_height(),t=h+autoscroll_px, hm=document.body.scrollHeight;
	if (t>=hm) {t=hm; autoscroll_dir=0;}
	window.scroll(0,t);
	return true
}
function import_script(url){
	var t = document.createElement("script");
	t.type="text/javascript";
	t.src = url;
	document.body.appendChild(t);
}
function overlay_init() {
	var d = document.createElement("div");
	d.id="overlay";
	d.style.width=document.documentElement.scrollWidth+"px";
	d.style.height=document.documentElement.scrollHeight+"px";
	document.body.appendChild(d);
	overlay_d=d;
	window.onresize = resize_cb;
}
function resize_cb() {
	overlay_d.style.width=document.documentElement.scrollWidth+"px";;
	overlay_d.style.height=document.documentElement.scrollHeight+"px";
}

function getAjax(url, q, success, failure) {
	if (window.XMLHttpRequest){
		// code for standard browsers Firefox, Chrome, Opera, Safari, and even IE7+
		xmlhttp=new XMLHttpRequest();
	} else {
		// code for IE6, IE5
		xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
	}
	xmlhttp.onreadystatechange=function() {
		if(xmlhttp.readyState==4) {
			if (xmlhttp.status==200) success(xmlhttp.responseText);
			else if (failure) failure();
		}
	}
	s="";
	for (var i in q) { s+="&"+i+"="+encodeURIComponent(q[i]); }
	s=url+"?"+s.slice(1);
	xmlhttp.open("GET",s,true);
	xmlhttp.send(null);
}
var needs_external_json=false;

var fromJson = function(t) {
	return eval("("+t+")");
}

function getJson(url, q, success, failure) {
	s=function(t){return success(fromJson(t));};
	getAjax(url, q, s, failure);
}

function html_escape(s) {
	return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;");
}

function re_escape(s) { return s.replace(/([.*+?^${}()|[\]\/\\])/g, '\\$1') }

function search_entry_focus(e) {
	e.setAttribute(klass, "search_active"+( e.getAttribute(klass) || "" ).replace("search_active","").replace("search_inactive",""));
	if (e.value == "نص البحث") e.value = "";
}
function search_entry_blur(e) {
	e.setAttribute(klass, "search_inactive"+( e.getAttribute(klass) || "" ).replace("search_active","").replace("search_inactive",""));
	if (e.value == "") e.value = "نص البحث";
}

function rm_class(e,c) {
  e.setAttribute(klass, ( e.getAttribute(klass) || "" ).replace(c,""));
  return false;
}

function init_get_by_class() {
if (document.getElementsByClassName == undefined) {
	document.getElementsByClassName = function(className)
	{
		var hasClassName = new RegExp("(?:^|\\s)" + className + "(?:$|\\s)");
		var allElements = document.getElementsByTagName("*");
		var results = [];

		var element;
		for (var i = 0; (element = allElements[i]) != null; i++) {
			var elementClass = element.className;
			if (elementClass && elementClass.indexOf(className) != -1 && hasClassName.test(elementClass))
				results.push(element);
		}

		return results;
	}
}
}

function init() {
	try {
		if (JSON) {
			var t=JSON.parse('"t"');
			fromJson = function(t) {
				return JSON.parse(t);
			}
		} else needs_external_json=true;
	} catch(e) {
		needs_external_json=true;
	}
	init_get_by_class();
	if (document.body.getAttribute(klass)!='body') {
		klass="className"; /* hack for ie */
	}
	setTimeout(animation_loop, 100);
	animations["_s_up"]=[autoscroll_up_cb];
	animations["_s_dn"]=[autoscroll_down_cb];
	overlay_init();
	var i;
	for (i in init_ls) init_ls[i]();
}

window.onload = init;

