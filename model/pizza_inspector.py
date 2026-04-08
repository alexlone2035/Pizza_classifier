from PIL import Image

class PizzaInspector:
    def __init__(self, classifier, detector):
        self.classifier = classifier
        self.detector = detector

        self.INGREDIENT_GROUPS = {
            'pepperoni': ['Pepperoni', 'pepperoni', 'Sausage'],
            'chicken': ['Chicken'],
            'mushroom': ['Mushroom', 'Mushrooms', 'mushrooms'],
            'tomato': ['Tomato', 'Tomatoes', 'tomato', 'tomatoes'],
            'pineapple': ['Pineapple', 'pineapple'],
            'bacon': ['Bacon'],
            'ham': ['Ham', 'Beef'],
            'shrimp': ['shrimp'],
            'cheese': ['Cheese', 'cheese'],
            'olive': ['Olive', 'Olives', 'black olives', 'black_olives'],
            'pepper': ['Pepper', 'Peppers', 'peppers', 'Bell Pepper', 'Green Pepper', 'Red Pepper'],
            'jalapeno': ['Jalapenoes'],
            'onion': ['Onion', 'Onions']
        }

        self.PIZZA_RULES = {
            "pepperoni": ["pepperoni"],
            "margarita": ["tomato"],
            "gavayskaya": ["pineapple", "chicken"],
            "vetchinaigriby": ["ham", "mushroom"],
            "slivochnayaskrevetkami": ["shrimp"],
            "tomatnayaskrevetkami": ["shrimp", "tomato"],
            "myasnaya": ["pepperoni", "bacon"],
            "myasnoebarbekyu": ["pepperoni", "bacon"],
            "vetchinaibekon": ["ham", "bacon"],
            "tsyplenokbarbekyu": ["chicken", "bacon"],
            "tsyplenokkordonblyu": ["chicken", "bacon"],
            "tsyplenokflorentina": ["chicken", "tomato"],
            "tsyplenokgrin": ["chicken", "pepper"],
            "tsyplenokkrench": ["chicken"],
            "sananasomibekonom": ["pineapple", "bacon"],
            "serdtsepepperoni_4syra": ["pepperoni"],
            "serdtsetsyplenokbarbekyu_pepperoni": ["chicken", "pepperoni"],
            "pepperonigrin": ["pepperoni", "pepper"],
            "bavarskaya": ["pepperoni"],
            "bolshayabonanza": ["pepperoni", "mushroom", "pepper"],
            "lyubimayapapinapitstsa": ["pepperoni", "mushroom", "pepper"],
            "malenkayaitaliya": ["pepperoni", "mushroom"],
            "superpapa": ["pepperoni", "mushroom", "olive", "pepper"],
            "chedderchizburger": ["bacon", "tomato"],
            "chizburger": ["tomato", "onion"],
            "cheddermeksikan": ["chicken", "jalapeno", "tomato"],
            "meksikanskaya": ["chicken", "jalapeno", "pepper"],
            "kaprichioza": ["mushroom", "olive"],
            "krem_chizsgribami": ["mushroom"],
            "lyubimayadedamoroza": ["pepperoni"],
            "lyubimayakarbonara": ["bacon"],
            "postnaya": ["mushroom", "tomato", "pepper"],
            "vegetarianskaya": ["mushroom", "tomato", "pepper", "olive"],
            "syrnaya": [],
            "chetyresyra": [],
            "pitstsa8syrovnew": [],
            "papamiks": ["any"],
            "miksgrin": ["any"],
            "palochki": ["any"],
            "novogodnyaya": ["any"],
            "rozhdestvenskaya": ["any"],
            "kosmicheskiyset23": ["any"],
            "ulybka": ["any"],
            "klubnikaizefir": ["any"],
            "sgrusheyibekonom": ["bacon"],
            "sgrusheyigolubymsyrom": ["any"],
            "grushabbq": ["chicken"],
            "alfredo": ["chicken"]
        }

    def inspect_pizza(self, image_path):
        try:
            image_pil = Image.open(image_path).convert('RGB')
            pizza_type, conf = self.classifier.predict(image_pil)
            raw_ingredients, yolo_data = self.detector.detect(image_path)
            counts = {}
            for group, keys in self.INGREDIENT_GROUPS.items():
                counts[group] = sum(raw_ingredients.get(k, 0) for k in keys)
            status = "OK"
            reason = "С пиццей все в порядке."
            problematic_ingredients = []
            required_ingredients = self.PIZZA_RULES.get(pizza_type, ["any"])

            if required_ingredients == []:
                meat_groups = ['pepperoni', 'chicken', 'bacon', 'ham', 'shrimp']
                for meat in meat_groups:
                    if counts[meat] > 0:
                        problematic_ingredients.append(meat)
                if problematic_ingredients:
                    status = "NOT_OK"
                    reason = f"{problematic_ingredients}"
            elif required_ingredients == ["any"]:
                for group_name, amount in counts.items():
                    if group_name != 'cheese' and 0 < amount < 8:
                        problematic_ingredients.append(group_name)
                if problematic_ingredients:
                    status = "NOT_OK"
                    reason = f"{problematic_ingredients}"

            else:
                for req in required_ingredients:
                    if counts[req] < 8:
                        problematic_ingredients.append(req)

                if problematic_ingredients:
                    status = "NOT_OK"
                    reason = f"{problematic_ingredients}"

            return {
                "success": True,
                "pizza_type": pizza_type,
                "confidence": round(conf, 2),
                "status": status,
                "reason": reason,
                "ingredients_found": raw_ingredients
            }

        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "reason": f"Ошибка обработки изображения: {str(e)}"
            }
