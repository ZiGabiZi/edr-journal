---
layout: page
title: Jurnal de parcurs
---

Notițele de lucru din spatele prototipului EDR: de ce a apărut fiecare
componentă și ce problemă concretă a rezolvat.

## Intrări

{% assign intrari = site.intrari | sort: "date" | reverse %}
{% for intrare in intrari %}
- **{{ intrare.date | date: "%d.%m.%Y" }}** · `{{ intrare.tip }}` ·
  [{{ intrare.title }}]({{ intrare.url | relative_url }}) — {{ intrare.rezumat }}
{% endfor %}
