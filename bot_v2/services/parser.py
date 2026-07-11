import re


class Parser:

    def parse(self, subject: str):

        print(f"[Parser] {subject}")

        scanner = ""

        if ":" in subject:
            scanner = subject.split(":")[0].strip()

        tickers = re.findall(
            r"\b[A-Z]{1,5}\b",
            subject,
        )

        blacklist = {
            "NEW",
            "ALERT",
            "SYMBOLS",
            "WERE",
            "ADDED",
            "TO",
            "SCAN",
            "THE",
            "AND",
        }

        tickers = [

            t

            for t in tickers

            if t not in blacklist

        ]

        return scanner, tickers


parser = Parser()
