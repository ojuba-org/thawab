#! /bin/bash
pushd thawab-themes/default/static/manual || {
  echo "can't change dir"
  exit 1
}
baseurl="http://www.ojuba.org/wiki/_export/xhtml/thawab/"
for i in manual
do
fn="${i:-index}.html"
i="${i:-الصفحة_الأولى}"
echo "getting $fn from ${baseurl}${i}"
rm "$fn" 2>/dev/null || :
curl -L -o "$fn" "${baseurl}${i}"

perl -i -lwne 'BEGIN{$echo=1;}
s:href="/wiki/thawab/([^"]+)":href="${1}.html":g;
s:src="/wiki/_media/thawab/([^?"]+)(\?[^"]*)?":src="images/$1":g;
s:href="/wiki/_detail/thawab/([^?"]+)(\?[^"]*)?":href="images/$1":g;
s!a href="http://!a target="_blank" href="http://!g;
if(/\<head[^>]*\>/){$echo=0;}
if(/#discussion__section|\<(link|meta|script)[^>]*\>/){next;}if (/class="tags"/) {$echo=0;}
if($echo){print $_;}if (/\<\/div\>/) {$echo=1;}
if(/\<\/head\>/) {
 print "<head>";
 print "<meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\" />";
 print "<title>دليل استخدام ثواب</title>";
 print "<link rel=\"stylesheet\" media=\"all\" type=\"text/css\" href=\"all.css\" />";
 print "<link rel=\"stylesheet\" media=\"screen\" type=\"text/css\" href=\"screen.css\" />";
 print "<link rel=\"stylesheet\" media=\"print\" type=\"text/css\" href=\"print.css\" />";
 print "</head>";
 $echo=1;
}
' "$fn"

done
popd

