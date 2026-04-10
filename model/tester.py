import os
import json
import torch
import numpy as np
import random
from Classifier_model.pizza_classifier import PizzaClassifier
from Detection_model.pizza_detector import PizzaDetector
from pizza_inspector import PizzaInspector


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


if __name__ == "__main__":

    set_seed(42)

    classifier = PizzaClassifier()
    detector = PizzaDetector()

    classifier.load_weights("Classifier_model/classifier.pth")
    detector.load_weights("Detection_model/yolo_best.pt")
    inspector = PizzaInspector(classifier, detector)

    test_dir = "../test_photos"

    if os.path.exists(test_dir):
        for filename in os.listdir(test_dir):
                img_path = os.path.join(test_dir, filename)
                print(f"\n[{filename}] --------------------")
                result = inspector.inspect_pizza(img_path)
                print(json.dumps(result, indent=4, ensure_ascii=False))

