import os
import torch
import torch.nn as nn
from torchvision import models, datasets, transforms
from torch.utils.data import DataLoader, random_split


class PizzaClassifier:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.weights_path = None
        self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        self.classes = []

    def train(self, dataset_dir, epochs=10, batch_size=16, save_path="classifier.pth", val_split=0.2, test_split=0.1):
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        full_dataset = datasets.ImageFolder(root=dataset_dir, transform=transform)
        self.classes = full_dataset.classes

        val_size = int(len(full_dataset) * val_split)
        test_size = int(len(full_dataset) * test_split)
        train_size = len(full_dataset) - val_size - test_size

        train_dataset, val_dataset, test_dataset = random_split(full_dataset, [train_size, val_size, test_size])

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

        self.model.fc = nn.Linear(self.model.fc.in_features, len(self.classes))
        self.model.to(self.device)

        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)

        for epoch in range(epochs):
            self.model.train()
            running_loss = 0.0

            for inputs, labels in train_loader:
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()

            self.model.eval()
            val_correct = 0
            val_total = 0
            with torch.no_grad():
                for inputs, labels in val_loader:
                    inputs, labels = inputs.to(self.device), labels.to(self.device)
                    outputs = self.model(inputs)
                    _, predicted = torch.max(outputs.data, 1)
                    val_total += labels.size(0)
                    val_correct += (predicted == labels).sum().item()

            val_acc = 100 * val_correct / val_total if val_total > 0 else 0
            print(
                f"Эпоха {epoch + 1}/{epochs}, Loss: {running_loss / len(train_loader):.4f}, Val Accuracy: {val_acc:.2f}%")

        print("\nЗапуск финального тестирования на отложенной выборке...")
        self.model.eval()
        test_correct = 0
        test_total = 0
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                outputs = self.model(inputs)
                _, predicted = torch.max(outputs.data, 1)
                test_total += labels.size(0)
                test_correct += (predicted == labels).sum().item()

        final_test_acc = 100 * test_correct / test_total if test_total > 0 else 0
        print(f"Итоговая точность на тестовых данных : {final_test_acc:.2f}%")

        self.weights_path = save_path
        torch.save({'state_dict': self.model.state_dict(), 'classes': self.classes}, self.weights_path)
        print(f"ResNet: Обучение завершено. Веса сохранены в {save_path}")

    def load_weights(self, weights_path="classifier.pth"):
        checkpoint = torch.load(weights_path, map_location=self.device, weights_only=False)
        self.classes = checkpoint['classes']
        self.model.fc = nn.Linear(self.model.fc.in_features, len(self.classes))
        self.model.load_state_dict(checkpoint['state_dict'])
        self.model.to(self.device)
        self.weights_path = weights_path
        self.model.eval()

    def predict(self, image_pil):

        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        img_tensor = transform(image_pil).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(img_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        return self.classes[predicted.item()], confidence.item()