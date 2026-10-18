"""World Predictor: Seldon-style "psychohistory" experiments built on Google's TimesFM.

Hari Seldon's psychohistory (Isaac Asimov, *Foundation*) claimed that the behaviour of very
large populations can be forecast statistically even though individuals cannot. This package
puts a modest, measurable version of that claim to the test with a modern time-series
foundation model, across three domains:

* ``news``    - attention paid to world events (GDELT news coverage volume)
* ``markets`` - stock indices, single stocks, and value stores such as gold and silver
* ``tech``    - interest in and adoption of new technologies (Wikipedia pageviews, Our World in Data)
"""

__version__ = "0.1.0"
