import polars
from random import randint

line_template = polars.DataFrame(
    schema={
        "Day": polars.String,
        "LineNo": int,
        "JpText": polars.String,
        "EngText": polars.String,
        "Speaker": polars.String
    }
)



#print(d.get_column("Arc"))
print(line_template.collect_schema())
for i in range(10):
    line_template.vstack(polars.DataFrame({"Day": str(randint(0, 10)),"LineNo": 23,  "JpText": "Hello", "EngText": "lmao", "Speaker": "Abdullah-chan"}), in_place=True)
#import time
#time.sleep(0.5)
#print(line_template)
#print(line_template.row(by_predicate=line_template.select("Day") == "4"))
# df = line_template[-1]
# line_template.extend()


print(line_template[-1:]["Day"].item())