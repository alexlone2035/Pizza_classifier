import os
import torch
import torch.nn as nn
from torchvision import models, datasets, transforms
from torch.utils.data import DataLoader


class PizzaClassifier:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.weights_path = None
        self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

    def train(self, dataset_dir, epochs=10, batch_size=16, save_path="classifier.pth"):
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        dataset = datasets.ImageFolder(root=dataset_dir, transform=transform)
        num_classes = len(dataset.classes)
        self.model.fc = nn.Linear(self.model.fc.in_features, num_classes)
        self.model.to(self.device)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.model.train()

        for epoch in range(epochs):
            running_loss = 0.0
            for inputs, labels in dataloader:
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()
            print(f"Эпоха {epoch + 1}/{epochs}, Loss: {running_loss / len(dataloader):.4f}")

        self.weights_path = save_path
        torch.save(self.model.state_dict(), self.weights_path)
        print(f"ResNet: Обучение завершено. Веса сохранены.")
        self.model.eval()

    def load_weights(self, weights_path="model/classifier.pth", dataset_dir="../classifier_dataset/train"):
        classes = sorted([d for d in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, d))])

        self.model.fc = nn.Linear(self.model.fc.in_features, len(classes))
        self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
        self.model.to(self.device)
        self.weights_path = weights_path

    def predict(self, image_pil, dataset_dir="../classifier_dataset/train"):
        if self.weights_path is None:
            raise RuntimeError("Модель не обучена!")

        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        folder_names = sorted([d for d in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, d))])

        self.model.eval()
        img_tensor = transform(image_pil).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(img_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        return folder_names[predicted.item()], confidence.item()
