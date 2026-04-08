import os
import json
import torch
import numpy as np
import random
from pizza_classifier import PizzaClassifier
from ingredient_detector import IngredientDetector
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
    detector = IngredientDetector()
    classifier.load_weights("classifier.pth")
    detector.load_weights("yolo_best.pt")
    inspector = PizzaInspector(classifier, detector)

    test_image = "../test1.jpg"
    if os.path.exists(test_image):
        result = inspector.inspect_pizza(test_image)
        print(json.dumps(result, indent=4, ensure_ascii=False))
