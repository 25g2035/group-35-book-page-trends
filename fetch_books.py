import csv
import os
import requests
import xml.etree.ElementTree as ET

def search_books(from_year, to_year, cnt_per_page, max_pages, start_idx):
    base_url = "https://ndlsearch.ndl.go.jp/api/opensearch"

    books = []
    for page in range(max_pages):
        params = {
            "any": "小説",
            "ndc": 9,    # 文学
            "from": str(from_year),
            "until": str(to_year),
            "cnt": cnt_per_page, # 最大取得件数（デフォルトは200件、最大で500件）
            "idx": start_idx,   # ページングしても501件目以降は取得できない
        }

        response = requests.get(base_url, params=params, timeout=150)

        #print(response.text)

        root = ET.fromstring(response.content)
        
        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
            "opensearch": "http://a9.com/-/spec/opensearchrss/1.0/"
        }

        items = root.findall(".//item")
        if not items:
            #print("これ以上データがありません。")
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

        # 次のページへ
        start_idx += cnt_per_page
        if len(items) < cnt_per_page:
            break

    return books

def search_month(y, m):
    date_str = f"{y}-{m:02}"
    from_year = date_str
    to_year = date_str
    books = search_books(from_year=from_year, to_year=to_year, cnt_per_page=500, max_pages=1, start_idx=1)
    print(f"{date_str}: {len(books)}件")
    return books

def search_year(y):
    books = []
    for m in range(1, 13):
        books.extend(search_month(y, m))
    return books

# tsvに出力
def write_tsv(name, books):
    output_file = f"data/{name}.tsv"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)    # dataフォルダがなければ作成
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "issued", "page_count"], delimiter="\t")
        writer.writeheader()
        writer.writerows(books)
    print(f"{len(books)}件のデータを {output_file} に保存しました。")

if __name__ == "__main__":
    # 使用例: 2020年から2025年までのデータを取得
    from_year = 2020
    to_year = 2025
    for y in range(from_year, to_year + 1):
        books = search_year(y)
        write_tsv(str(y), books)
