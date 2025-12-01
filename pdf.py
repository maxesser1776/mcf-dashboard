from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

file_path = "../Capital_Flows_Metrics_Explained.pdf"

styles = getSampleStyleSheet()
story = []

content = """
Capital Flows Metrics — Dashboard Explanations

1. Fed Liquidity & Plumbing
Shows if money is expanding and flowing freely via Fed balance sheet, TGA, RRP, and funding spreads.
More liquidity + low stress → flows into risk.
Less liquidity + stress → flows into USD & Treasuries.

2. Yield Curve & Policy
Steep curve → confidence in future growth → capital into long-duration & equities.
Inverted curve → recession fears → capital shortens duration & de-risks.

3. Credit Spreads (IG & HY)
Tight spreads → risk appetite, lending strong.
Wide spreads → risk-off, flight to quality.

4. FX Liquidity (USD vs EM)
Strong USD → global deleveraging, capital exits EM risk.
Weak USD → capital flows outward into global & EM assets.

5. Volatility & Market Stress (VIX, MOVE)
Low vol = leverage + carry increase, risk-on flows.
High vol = deleveraging, capital retreats to safety.

6. Growth & Inflation (Macro Core)
Healthy growth + controlled inflation → flows into equities & cyclicals.
Overheating inflation or falling growth → defensive rotation.

7. Leading Growth Signals (Orders vs Inventories + Claims)
Orders > inventories + low claims → rising demand → flows into cyclicals.
Orders < inventories + rising claims → slowdown → flows into duration + USD.

"""

# Build PDF
doc = SimpleDocTemplate(file_path, pagesize=letter)

for para in content.strip().split("\n\n"):
    story.append(Paragraph(para.replace("\n", "<br/>"), styles["Normal"]))
    story.append(Spacer(1, 12))

doc.build(story)

file_path
