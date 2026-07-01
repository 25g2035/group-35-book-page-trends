import csv
import math
import os
import re
import statistics
import time
import unicodedata
import requests
import xml.etree.ElementTree as ET


def is_valid_isbn(isbn):
    isbn = re.sub(r"[^0-9Xx]", "", isbn or "").upper()
    if len(isbn) == 10:
        total = 0
        for i, char in enumerate(isbn):
            if char == "X":
                if i != 9:
                    return False
                value = 10
            else:
                value = int(char)
            total += value * (10 - i)
        return total % 11 == 0

    if len(isbn) == 13 and isbn.isdigit():
        total = 0
        for i, char in enumerate(isbn[:12]):
            total += int(char) * (1 if i % 2 == 0 else 3)
        check_digit = (10 - total % 10) % 10
        return check_digit == int(isbn[-1])

    return False


def get_isbn(item, ns):
    identifiers = item.findall("dc:identifier", namespaces=ns)
    for identifier in identifiers:
        text = identifier.text or ""
        matches = re.findall(r"(?:97[89][-\s]?)?\d[-\s]?\d{2,5}[-\s]?\d{2,7}[-\s]?[\dXx]", text)
        for match in matches:
            isbn = re.sub(r"[^0-9Xx]", "", match).upper()
            if is_valid_isbn(isbn):
                return isbn
    return ""


def normalize_text(text):
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\s・／/　]+", "", text)
    return text.lower()


def get_book_key(book):
    isbn = re.sub(r"[^0-9Xx]", "", book.get("isbn") or "").upper()
    if is_valid_isbn(isbn):
        return ("isbn", isbn)
    return (
        "book",
        normalize_text(book.get("title")),
        normalize_text(book.get("creator")),
        normalize_text(book.get("publisher")),
    )


def remove_duplicates(books):
    result = []
    seen = set()
    for book in books:
        key = get_book_key(book)
        if key in seen:
            continue
        seen.add(key)
        result.append(book)
    return result


def has_page_count(book):
    page_count = book.get("page_count")
    return page_count is not None and str(page_count).strip() != ""


def percentile(sorted_values, p):
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * (p / 100)
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return sorted_values[int(k)]
    return sorted_values[lower] * (upper - k) + sorted_values[upper] * (k - lower)


def print_page_stats(books, label=None):
    page_counts = sorted(int(book["page_count"]) for book in books if has_page_count(book))
    if not page_counts:
        # print("ページ数があるデータがないため、統計を表示できません。")
        return
        return

    count = len(page_counts)
    mean = statistics.mean(page_counts)
    median = statistics.median(page_counts)
    variance = statistics.variance(page_counts) if count >= 2 else 0
    pstdev = statistics.pstdev(page_counts)
    stdev = statistics.stdev(page_counts) if count >= 2 else 0
    modes = statistics.multimode(page_counts)
    q1 = percentile(page_counts, 25)
    q3 = percentile(page_counts, 75)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outlier_count = sum(1 for x in page_counts if x < lower_fence or x > upper_fence)

    # 年代ラベルと数値のみを改行区切りで出力
    print("")
    if label:
        print(label)
    print("")
    print(count)
    print(min(page_counts))
    print(max(page_counts))
    print(max(page_counts) - min(page_counts))
    print(sum(page_counts))
    print(f"{mean:.2f}")
    print(f"{median:.2f}")
    print(",".join(str(m) for m in modes[:10]))
    print(f"{variance:.2f}")
    print(f"{stdev:.2f}")
    print(f"{pstdev:.2f}")
    print(f"{q1:.2f}")
    print(f"{q3:.2f}")
    print(f"{iqr:.2f}")
    print(f"{percentile(page_counts, 10):.2f}")
    print(f"{percentile(page_counts, 90):.2f}")
    print(outlier_count)
    print(sum(1 for x in page_counts if x < 100))
    print(sum(1 for x in page_counts if x >= 500))
    print("")


def search_books(from_year, to_year, cnt_per_page=500, max_pages=None, start_idx=1):
    base_url = "https://ndlsearch.ndl.go.jp/api/opensearch"

    books = []
    page = 0
    while max_pages is None or page < max_pages:
        params = {
            "any": "小説",
            "ndc": 9,    # 文学
            "from": str(from_year),
            "until": str(to_year),
            "cnt": cnt_per_page, # 最大取得件数（デフォルトは200件、最大で500件）
            "idx": start_idx,   # 501件目以降はidxを進めて取得する
        }

        for retry in range(4):
            response = requests.get(base_url, params=params, timeout=60)
            if response.status_code != 429:
                response.raise_for_status()
                break
            wait_seconds = 2 ** retry
            # print(f"HTTP 429のため {wait_seconds} 秒待って再試行します。")
            time.sleep(wait_seconds)
        else:
            response.raise_for_status()

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
                match = re.search(r"(\d+)\s*p", extent)
                if match:
                    page_count = int(match.group(1))
            if page_count is None:
                continue

            # レコード追加
            book = {
                #"issued": item.findtext("dcterms:issued", namespaces=ns),   # 出版年
                "page_count": page_count,    # ページ数
                "title": item.findtext("title"),    # タイトル
                "creator": item.findtext("dc:creator", namespaces=ns),
                "publisher": item.findtext("dc:publisher", namespaces=ns),
                "isbn": get_isbn(item, ns),
                "link": item.findtext("link")
            }
            books.append(book)

        # 次のページへ
        page += 1
        start_idx += cnt_per_page
        if len(items) < cnt_per_page:
            break

        time.sleep(1)

    return remove_duplicates(books)


def search_month(y, m):
    date_str = f"{y}-{m:02}"
    from_year = date_str
    to_year = date_str
    books = search_books(from_year=from_year, to_year=to_year, cnt_per_page=500, max_pages=None, start_idx=1)
    # print(f"{date_str}: {len(books)}件")

    for book in books:
        book["year"] = y
        book["month"] = m
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
    books = [book for book in books if has_page_count(book)]
    books = remove_duplicates(books)
    if os.path.exists(output_file):
        # print(f"{output_file} は既にあるため上書きします。")
        pass
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "month", "page_count", "title", "creator", "publisher", "isbn", "link"], delimiter="\t")
        writer.writeheader()
        writer.writerows(books)
    # print(f"{len(books)}件のデータを {output_file} に保存しました。")
    print_page_stats(books, name)


def search_years_and_write_tsv(from_year, to_year):
    books = []
    for y in range(from_year, to_year + 1):
        books.extend(search_year(y))
    write_tsv(f"{from_year}-{to_year}", books)
    return books


if __name__ == "__main__":
    # 使用例: 1990年から1999年までのデータを取得しTSVファイルを出力
    for y in range(1990, 2000):
        search_years_and_write_tsv(y, y)
