"""Does cv2.phaseCorrelate with a window modify its inputs? Prints the version and the answer."""
import cv2
import numpy as np


def main() -> None:
    rng = np.random.default_rng(0)
    a = rng.random((64, 64)).astype(np.float32)
    b = np.roll(a, 1, axis=1).copy()
    win = cv2.createHanningWindow((64, 64), cv2.CV_32F)
    a0, b0 = a.copy(), b.copy()
    first, _ = cv2.phaseCorrelate(a, b, win)
    second, _ = cv2.phaseCorrelate(a, b, win)
    print(f"opencv {cv2.__version__}")
    print(f"src1 changed: {not np.array_equal(a, a0)}  src2 changed: {not np.array_equal(b, b0)}")
    print(f"first call shift: ({first[0]:.4f}, {first[1]:.4f})  repeat call: ({second[0]:.4f}, {second[1]:.4f})")


if __name__ == "__main__":
    main()
