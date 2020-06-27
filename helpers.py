import os, requests

def get_goodreads(isbn):
    response = requests.get("https://www.goodreads.com/book/review_counts.json",
                            {"key": " f761iEQLxnpaSwWCtNhO0g", "isbns": isbn})
    
    return response

def main():
    return 0


if __name__ == "__main__":
    main()