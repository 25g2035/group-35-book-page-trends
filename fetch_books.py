import requests
import xml.etree.ElementTree as ET

def search_books(from_year, to_year, start_idx=1, cnt_per_page=100, max_pages=20):
    base_url = "https://ndlsearch.ndl.go.jp/api/opensearch"

    books = []
    for page in range(max_pages):
        params = {
            "any": "小説",
            "ndc": 9,    # 文学
            "from": str(from_year),
            "until": str(to_year),
            "cnt": cnt_per_page,
        }

        response = requests.get(base_url, params=params, timeout=15)

        #print(response.text)

        root = ET.fromstring(response.content)
        
        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
            "opensearch": "http://a9.com/-/spec/opensearchrss/1.0/"
        }

        items = root.findall(".//item")
        if not items:
            print("これ以上データがありません。")
            break

        for item in root.findall(".//item"):
            # ページ数取得
            extent = item.findtext("dc:extent", namespaces=ns)
            page_count = None
            if extent:
                import re
                match = re.search(r'(\d+)', extent)
                if match:
                    page_count = int(match.group(1))

            # レコード追加
            book = {
                "issued": item.findtext("dcterms:issued", namespaces=ns),   # 出版年
                "page_count": page_count,    # ページ数
                "title": item.findtext("title"),    # タイトル
                #"creator": item.findtext("dc:creator", namespaces=ns),
                #"publisher": item.findtext("dc:publisher", namespaces=ns),
                #"isbn": item.findtext("dc:identifier", namespaces=ns),
                #"link": item.findtext("link")
            }
            books.append(book)

        print(len(books))

        # 次のページへ
        start_idx += cnt_per_page
        if len(items) < cnt_per_page:
            break

    return books

# 使用例
books = search_books(from_year=2020, to_year=2020, max_pages=20)
for book in books:
    print(book)
print(f"取得した冊数: {len(books)}")
