# Offline scoring prototype

It is a sample deterministic scoring step. It relies on structured data fields which were hand curated; it does not process PDFs, OCR, LLMs, source quotation validations or license validations with some external service.

To run from repository root directory:

```bash
python prototype/score.py
python -m unittest discover -s prototype/tests -p "test_*.py"
```

Admin can change the scoring weights and anchors for formulas in `criteria.json`. The program will validate the sum of the weights equals 100 and all scoring components have `max_points` value equal to their weights.