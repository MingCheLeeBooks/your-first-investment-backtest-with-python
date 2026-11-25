# Your First Investment Backtest with Python

Companion materials for the edition with the QQQ comparison through December 2025.

## Download and run

- [Download the Notebook](https://github.com/MingCheLeeBooks/your-first-investment-backtest-with-python/raw/refs/heads/main/Investment_Backtest_Labs_2025.ipynb). In Google Colab, choose **File → Upload notebook** and select the file. You can also open it with Jupyter.
- [Download the Python examples](https://github.com/MingCheLeeBooks/your-first-investment-backtest-with-python/raw/refs/heads/main/examples.py). Run `python examples.py` or `python3 examples.py` in the folder containing the file.
- Use Python 3.11 or later. The examples use the standard library.

Run Notebook cells from top to bottom. The historical data cells need internet access on first use. The July practice case includes its price rows and can run offline. In Exercise 13, change `cutoff` to use another end date. If the date is a weekend or market holiday, the exercise uses the last available session on or before it.

## Check your output

With a cutoff of December 31, 2025, the full-period buy-and-hold example should show an ending value of **$1,964.49** on a $1,000 starting balance. The book also covers staged purchases and a 20-session moving-average rule. The historical examples use QQQ price data, exclude distributions, and apply the costs specified in the book. They are for education.
