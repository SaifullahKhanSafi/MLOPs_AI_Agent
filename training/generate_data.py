from pathlib import Path

from sklearn.datasets import load_iris


def main():
    path = Path("data/iris.csv")
    path.parent.mkdir(exist_ok=True)
    frame = load_iris(as_frame=True).frame
    frame.columns = ["sepal_length", "sepal_width", "petal_length", "petal_width", "target"]
    frame.to_csv(path, index=False, lineterminator="\n")
    print(f"Generated {len(frame)} rows: {path}")


if __name__ == "__main__":
    main()
