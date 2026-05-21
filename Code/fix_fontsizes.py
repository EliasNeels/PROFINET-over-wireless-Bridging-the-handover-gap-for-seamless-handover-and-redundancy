"""Reset all font sizes in plot_engine.py to original + 2."""

with open('plot_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix rcParams block - revert from huge values to original+2
# Original:  font.size=18, labelsize=20, titlesize=22, legend=16, tick=16, figtitle=24
# Target (+2): 20, 22, 24, 18, 18, 26
rcparam_replacements = [
    ('"font.size": 32', '"font.size": 20'),
    ('"axes.labelsize": 36', '"axes.labelsize": 22'),
    ('"axes.titlesize": 38', '"axes.titlesize": 24'),
    ('"legend.fontsize": 30', '"legend.fontsize": 18'),
    ('"xtick.labelsize": 30', '"xtick.labelsize": 18'),
    ('"ytick.labelsize": 30', '"ytick.labelsize": 18'),
    ('"figure.titlesize": 42', '"figure.titlesize": 26'),
]
for old, new in rcparam_replacements:
    content = content.replace(old, new)

# Fix hardcoded fontsizes back to original+2
# Current (huge) -> target (original+2)
# original: 28->30, 24->26, 22->24, 20->22, 18->20, 16->18, 14->16, 13->15
fontsize_replacements = [
    ('fontsize=44', 'fontsize=30'),  # was 28 -> +2 = 30
    ('fontsize=36', 'fontsize=26'),  # was 24 -> +2 = 26
    ('fontsize=34', 'fontsize=24'),  # was 22 -> +2 = 24
    ('fontsize=32', 'fontsize=22'),  # was 20 -> +2 = 22
    ('fontsize=30', 'fontsize=20'),  # was 18 -> +2 = 20
    ('fontsize=28', 'fontsize=18'),  # was 16 -> +2 = 18
    ('fontsize=26', 'fontsize=16'),  # was 14 -> +2 = 16
    ('fontsize=24', 'fontsize=15'),  # was 13 -> +2 = 15
]
for old, new in fontsize_replacements:
    content = content.replace(old, new)

with open('plot_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done - fonts set to original + 2')
