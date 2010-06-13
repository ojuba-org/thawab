/**
 *
 * copyright © 2010 ojuba.org, Muayyad Saleh Alsadi
 *
 **/
var th_hash;
function mini_search_row_factory(u, bu, r) {
  return "<tr><td><a onmouseover='asynctip(this);' onmouseout='asynctip_hide(this);' rel='"+u+r.i+"' href='#"+encodeURI(r.n)+"'>"+ html_escape(r.t)+"</a></td><td>"+html_escape(r.r)+"</td>\n";
}
resultsPerPage=10; // defined in main.js
search_row_factory=mini_search_row_factory;
function doMiniSearch(q) {
  doSearch(q+" كتاب:"+kitabId);
}

function view_cb(h) {
	var l,n;
	th_hash=h;
	l=document.getElementById("loading");
	l.style.display="block";
	if (! h) h="_i0";
	getJson(script+"/json/view/"+kitabUid+"/"+h, {}, 
		function (d) {
			document.getElementById("maincontent").innerHTML=d.content;
			document.getElementById("subtoc").innerHTML=d.childrenLinks;
			document.getElementById("breadcrumbs").innerHTML=d.breadcrumbs;
			n=document.getElementById("prevLink");
			n.setAttribute('title', d.prevTitle);
			n.setAttribute('href', d.prevUrl);
			n=document.getElementById("upLink");
			n.setAttribute('title', d.upTitle);
			n.setAttribute('href', d.upUrl);
			n=document.getElementById("nextLink");
			n.setAttribute('title', d.nextTitle);
			n.setAttribute('href', d.nextUrl);
			l.style.display="none"; /* should be faded */
		},
		function () {
			l.style.display="none"; /* should show error */
		}
	);

	return false;
}

function ajax_check_hash() {
	if (window.location.hash==("#"+th_hash)) return true;
	view_cb(window.location.hash.slice(1));
	return true;
}

function th_view_init() {
	var l;
	l=document.location.toString();
	loc=window.location.hash.slice(1);
	if (loc=="") document.location=l+"#_i0";
	else view_cb(loc);
}

animations["_ajax_check_hash"]=[ajax_check_hash];
init_ls.push(th_view_init);

