def get_distance(a, b):
    l0 = torch.norm((a - b).view(a.shape[0], -1), p=0, dim=1)
    l2 = torch.norm((a - b).view(a.shape[0], -1), p=2, dim=1)
    mse = (a - b).view(a.shape[0], -1).pow(2).mean(1)
    linf = torch.norm((a - b).view(a.shape[0], -1), p=float('inf'), dim=1)
    return l0, l2, mse, linf


"""
===============================================================================
:mod:`foolbox.criteria`
===============================================================================

Criteria are used to define which inputs are adversarial.
We provide common criteria for untargeted and targeted adversarial attacks,
e.g. :class:`Misclassification` and :class:`TargetedMisclassification`.
New criteria can easily be implemented by subclassing :class:`Criterion`
and implementing :meth:`Criterion.__call__`.

Criteria can be combined using a logical and ``criterion1 & criterion2``
to create a new criterion.


:class:`Misclassification`
===============================================================================

.. code-block:: python

   from foolbox.criteria import Misclassification
   criterion = Misclassification(labels)

.. autoclass:: Misclassification
   :members:


:class:`TargetedMisclassification`
===============================================================================

.. code-block:: python

   from foolbox.criteria import TargetedMisclassification
   criterion = TargetedMisclassification(target_classes)

.. autoclass:: TargetedMisclassification
   :members:


:class:`Criterion`
===============================================================================

.. autoclass:: Criterion
   :members:
   :special-members: __call__
"""
from typing import TypeVar, Any
from abc import ABC, abstractmethod
import eagerpy as ep
import torch


T = TypeVar("T")


class Criterion(ABC):
    """Abstract base class to implement new criteria."""

    @abstractmethod
    def __repr__(self) -> str:
        ...

    @abstractmethod
    def __call__(self, perturbed: T, outputs: T) -> T:
        """Returns a boolean tensor indicating which perturbed inputs are adversarial.

        Args:
            perturbed: Tensor with perturbed inputs ``(batch, ...)``.
            outputs: Tensor with model outputs for the perturbed inputs ``(batch, ...)``.

        Returns:
            A boolean tensor indicating which perturbed inputs are adversarial ``(batch,)``.
        """
        ...

    def __and__(self, other: "Criterion") -> "Criterion":
        return _And(self, other)


class _And(Criterion):
    def __init__(self, a: Criterion, b: Criterion):
        super().__init__()
        self.a = a
        self.b = b

    def __repr__(self) -> str:
        return f"{self.a!r} & {self.b!r}"

    def __call__(self, perturbed: T, outputs: T) -> T:
        args, restore_type = ep.astensors_(perturbed, outputs)
        a = self.a(*args)
        b = self.b(*args)
        is_adv = ep.logical_and(a, b)
        return restore_type(is_adv)


class Misclassification(Criterion):
    """Considers those perturbed inputs adversarial whose predicted class
    differs from the label.

    Args:
        labels: Tensor with labels of the unperturbed inputs ``(batch,)``.
    """

    def __init__(self, labels: Any):
        super().__init__()
        self.labels: ep.Tensor = ep.astensor(labels)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.labels!r})"

    def __call__(self, perturbed: T, outputs: T) -> T:
        outputs_, restore_type = ep.astensor_(outputs)
        del perturbed, outputs

        classes = outputs_.argmax(axis=-1)
        assert classes.shape == self.labels.shape
        is_adv = classes != self.labels
        return restore_type(is_adv)


class TargetedMisclassification(Criterion):
    """Considers those perturbed inputs adversarial whose predicted class
    matches the target class.

    Args:
        target_classes: Tensor with target classes ``(batch,)``.
    """

    def __init__(self, target_classes: Any):
        super().__init__()
        self.target_classes: ep.Tensor = ep.astensor(target_classes)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.target_classes!r})"

    def __call__(self, perturbed: T, outputs: T) -> T:
        outputs_, restore_type = ep.astensor_(outputs)
        del perturbed, outputs

        classes = outputs_.argmax(axis=-1)
        assert classes.shape == self.target_classes.shape
        is_adv = classes == self.target_classes
        return restore_type(is_adv)


class TargetedMisclassificationWithProbability(Criterion):
    def __init__(self, target_classes: Any, prob: Any):
        super().__init__()
        self.target_classes: ep.Tensor = ep.astensor(target_classes)
        self.prob = prob

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.target_classes!r})"

    def __call__(self, perturbed: T, outputs: T) -> T:
        outputs_, restore_type = ep.astensor_(outputs)
        del perturbed, outputs

        classes = outputs_.argmax(axis=-1)
        assert classes.shape == self.target_classes.shape
        percentages = ep.astensor(torch.nn.functional.softmax(outputs_, dim=-1))
        one_hot_labels = torch.eye(len(outputs_[0]))[self.target_classes.raw]
        probs = ep.astensor(torch.masked_select(percentages.raw, one_hot_labels.bool()))
        compared = ep.astensor(torch.full_like(probs.raw, self.prob))
        is_adv = ep.astensor(torch.logical_and(classes.raw == self.target_classes.raw, probs.raw >= compared.raw))
        return restore_type(is_adv)


class TempCriterion(Criterion):
    def __init__(self, target_images: Any, distance: Any, metric: Any, logged: Any):
        super().__init__()
        self.target_images: ep.Tensor = ep.astensor(target_images)
        self.distance = distance
        self.metric = metric
        self.logged = logged

    def __repr__(self) -> str:
        return f"Hello World!"

    def __call__(self, perturbed: T, outputs: T) -> T:
        outputs_, restore_type = ep.astensor_(outputs)
        del perturbed, outputs

        l0, l2, mse, linf = get_distance(self.target_images.raw, outputs_.raw)
        # print('MSE', mse)
        if self.metric == 'l0':
            is_adv = ep.astensor(l0 <= self.distance)
        elif self.metric == 'l2':
            is_adv = ep.astensor(l2 <= self.distance)
        elif self.metric == 'mse':
            is_adv = ep.astensor(mse <= self.distance)
        elif self.metric == 'linf':
            is_adv = ep.astensor(linf <= self.distance)
        # print('is_adv', is_adv)
        
        if self.logged:
            print('MSE', mse)
            print('is_adv', is_adv)
         
        return restore_type(is_adv)
