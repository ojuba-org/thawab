/**
 *
 * copyright © 2010 ojuba.org, Muayyad Saleh Alsadi
 *
 **/
var last_highlighted="";
var th_hash;
function mini_search_row_factory(u, bu, r) {
  return "<tr><td><a onmouseover='asynctip(this);' onmouseout='asynctip_hide(this);' rel='"+u+r.i+"' href='#"+encodeURI(r.n)+"'>"+ html_escape(r.t)+"</a></td><td>"+html_escape(r.r)+"</td>\n";
}
function mini_search_row_factory_st(u, bu, r) {
  return "<tr><td><a onmouseover='asynctip(this);' onmouseout='asynctip_hide(this);' rel='"+u+r.i+"' href='./"+encodeURI(r.n)+".html'>"+ html_escape(r.t)+"</a></td><td>"+html_escape(r.r)+"</td>\n";
}
resultsPerPage=10; // defined in main.js
search_row_factory=(is_static)?mini_search_row_factory_st:mini_search_row_factory;
function doMiniSearch(q) {
  doSearch(q+" كتاب:"+kitabId);
}

function view_cb(h) {
	var l,n;
	window.scroll(0,0);
	l=document.getElementById("loading");
	l.style.display="block";
	if (! h) h="_i0";
	th_hash=h;
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
			highlight_words(document.getElementById("maincontent"), highlighted, true);
		},
		function () {
			l.style.display="none"; /* should show error */
		}
	);

	return false;
}

function ajax_check_hash() {
	var h=window.location.hash;
	if (h==("#"+th_hash)) return true;
	view_cb(h.slice(1));
	return true;
}

var harakat="ًٌٍَُِّْـ";

function highlight_word(o, w, i) {
	w=w.trim();
	if (w=="") return;
	w=re_escape(w).replace(/(\\?.)/g, "$1[\-_"+harakat+"]*");
	w="("+w+")";
	var re = new RegExp( w, "gi");
	a=o.innerHTML.split(/(<\/?[^>]*>)/);
	for (j in a) {
		s=a[j];
		if (s && s[0]!="<") {
			a[j]=s.replace(re, "<span class='highlight term"+i+"'>$1</span>");
		}
	}
	o.innerHTML=a.join("");
}

function highlight_words(o, w, scroll) {
	var i,a=w.split(" ");
	highlight_words_off(o);
	for (i in a) {
		highlight_word(o,a[i],i);
	}
	if (scroll) scroll_to_first_highlighted();
}

function scroll_to_first_highlighted() {
	a=document.getElementsByClassName("highlight");
	for (j=0;j<a.length;++j) {
		a[j].scrollIntoView();
		break;
	}
}

function highlight_words_off(o) {
	o.innerHTML=o.innerHTML.replace(/\<span class=["']highlight term\d+['"]\>([^<>]*)<\/span>/gi, "$1");
}

var highlighting=false;

function highlight_cb() {
	if (highlighting) return true;
	var q=document.getElementById('q').value;
	if (q=="نص البحث") return true;
	highlighting=true;
	highlighted=q;
	if (last_highlighted!=highlighted) {
		last_highlighted=highlighted;
		highlight_words(document.getElementById("maincontent"), highlighted, false);
	}
	highlighting=false;
	return true;
}


function th_view_init() {
	var l;
	if (!is_static) {
		l=document.location.toString();
		loc=window.location.hash.slice(1);
		if (loc=="") document.location=l+"#_i0";
		else view_cb(loc);
	}
	/* hide mini-search if not indexed */
	if (!is_indexed) {
		document.getElementById("minisearch").style.display="none";
		document.getElementById("nominisearch").style.display="block";
	}
	highlighted=get_url_vars()["highlight"] || "";
	highlight_words(document.getElementById("maincontent"), highlighted, true);
	last_highlighted=highlighted;
}
search_done=scroll_to_first_highlighted;
animations["_highlight"]=[highlight_cb];
if (!is_static) animations["_ajax_check_hash"]=[ajax_check_hash];
init_ls.push(th_view_init);
