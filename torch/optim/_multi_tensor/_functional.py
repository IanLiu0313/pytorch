r"""Functional interface"""
import math
import torch
from torch import Tensor
from typing import List


def adamax(params: List[Tensor],
           grads: List[Tensor],
           exp_avgs: List[Tensor],
           exp_infs: List[Tensor],
           state_steps: List[Tensor],
           *,
           beta1: float,
           beta2: float,
           lr: float,
           weight_decay: float,
           eps: float):
    r"""Functional API that performs Adamax algorithm computation.

    See :class:`~torch.optim.Adamax` for details.
    """

    if not all([isinstance(t, torch.Tensor) for t in state_steps]):
        raise RuntimeError("API has changed, `state_steps` argument must contain a list of singleton tensors")

    # Update steps
    torch._foreach_add_(state_steps, 1)

    if weight_decay != 0:
        torch._foreach_add_(grads, params, alpha=weight_decay)

    # Update biased first moment estimate.
    torch._foreach_mul_(exp_avgs, beta1)
    torch._foreach_add_(exp_avgs, grads, alpha=1 - beta1)

    # Update the exponentially weighted infinity norm.
    torch._foreach_mul_(exp_infs, beta2)

    for exp_inf, grad in zip(exp_infs, grads):
        norm_buf = torch.cat([
            exp_inf.unsqueeze(0),
            grad.abs().add_(eps).unsqueeze_(0)
        ], 0)
        torch.max(norm_buf, 0, keepdim=False, out=(exp_inf, exp_inf.new().long()))

    bias_corrections = [1 - beta1 ** step.item() for step in state_steps]
    clr = [-1 * (lr / bias_correction) for bias_correction in bias_corrections]
    torch._foreach_addcdiv_(params, exp_avgs, exp_infs, clr)


def asgd(params: List[Tensor],
         grads: List[Tensor],
         axs: List[Tensor],
         mus: List[Tensor],
         etas: List[Tensor],
         state_steps: List[Tensor],
         *,
         lambd: float,
         lr: float,
         t0: float,
         alpha: float,
         weight_decay: float):
    r"""Functional API that performs ASGD algorithm computation.
    See :class:`~torch.optim.ASGD` for details.
    """

    # update step
    torch._foreach_add_(state_steps, 1)

    if weight_decay != 0:
        torch._foreach_add_(grads, params, alpha=weight_decay)

    # decay term
    eta = etas[0].item()
    torch._foreach_mul_(params, 1 - lambd * eta)

    # update parameter
    torch._foreach_add_(params, grads, alpha=-eta)

    # averaging
    for i in range(len(axs)):
        if mus[i].item() != 1:
            axs[i].add_(params[i].sub(axs[i]).mul(mus[i]))
        else:
            axs[i].copy_(params[i])

    # update eta and mu
    for i in range(len(mus)):
        new_eta = torch.tensor(lr / math.pow((1 + lambd * lr * state_steps[i].item()), alpha))
        etas[i].copy_(new_eta)
        new_mu = torch.tensor(1 / max(1, state_steps[i].item() - t0))
        mus[i].copy_(new_mu)


def radam(params: List[Tensor],
          grads: List[Tensor],
          exp_avg: List[Tensor],
          exp_avg_sq: List[Tensor],
          state_steps: List[Tensor],
          *,
          beta1: float,
          beta2: float,
          lr: float,
          weight_decay: float,
          eps: float):
    r"""Functional API that performs RAdam algorithm computation.

    See :class:`~torch.optim.RAdam` for details.
    """

    if not all([isinstance(t, torch.Tensor) for t in state_steps]):
        raise RuntimeError("API has changed, `state_steps` argument must contain a list of singleton tensors")

    # Update steps
    torch._foreach_add_(state_steps, 1)

    # maximum length of the approximated SMA
    rho_inf = 2 / (1 - beta2) - 1
    # compute the length of the approximated SMA
    rho_t_list = [rho_inf - 2 * step.item() * (beta2 ** step.item()) / (1 - beta2 ** step.item()) for step in state_steps]

    bias_correction1 = [1 - beta1 ** step.item() for step in state_steps]
    bias_correction2 = [1 - beta2 ** step.item() for step in state_steps]
    if weight_decay != 0:
        torch._foreach_add_(grads, params, alpha=weight_decay)

    # Decay the first and second moment running average coefficient
    torch._foreach_mul_(exp_avg, beta1)
    torch._foreach_add_(exp_avg, grads, alpha=1 - beta1)

    torch._foreach_mul_(exp_avg_sq, beta2)
    torch._foreach_addcmul_(exp_avg_sq, grads, grads, 1 - beta2)

    rect = [math.sqrt((rho_t - 4) * (rho_t - 2) * rho_inf / ((rho_inf - 4) * (rho_inf - 2) * rho_t))
            if rho_t > 5 else 0 for rho_t in rho_t_list]
    unrectified = [0 if rect > 0 else 1. for rect in rect]

    exp_avg_sq_sqrt = torch._foreach_sqrt(exp_avg_sq)
    bias_correction_sqrt = [math.sqrt(bc) for bc in bias_correction2]
    denom = torch._foreach_div(exp_avg_sq_sqrt, bias_correction_sqrt)
    step_size = [(lr * rect / bc) * -1 for rect, bc in zip(rect, bias_correction1)]
    torch._foreach_addcdiv_(params, exp_avg, denom, step_size)

    denom = [torch.ones_like(exp_av, memory_format=torch.preserve_format) for exp_av in exp_avg]
    step_size = [(lr * rect / bc) * -1 for rect, bc in zip(unrectified, bias_correction1)]
    torch._foreach_addcdiv_(params, exp_avg, denom, step_size)


def nadam(params: List[Tensor],
          grads: List[Tensor],
          exp_avg: List[Tensor],
          exp_avg_sq: List[Tensor],
          mu_products: List[Tensor],
          state_steps: List[Tensor],
          *,
          beta1: float,
          beta2: float,
          lr: float,
          weight_decay: float,
          momentum_decay: float,
          eps: float):
    r"""Functional API that performs NAdam algorithm computation.
    See :class:`~torch.optim.NAdam` for details.
    """

    if not all([isinstance(t, torch.Tensor) for t in state_steps]):
        raise RuntimeError("API has changed, `state_steps` argument must contain a list of singleton tensors")

    if not all([isinstance(t, torch.Tensor) for t in mu_products]):
        raise RuntimeError("API has changed, `mu_products` argument must contain a list of singleton tensors")

    # update steps
    torch._foreach_add_(state_steps, 1)

    bias_correction1 = [1 - beta1 ** step.item() for step in state_steps]
    bias_correction2 = [1 - beta2 ** step.item() for step in state_steps]
    mus = [beta1 * (1. - 0.5 * (0.96 ** (step.item() * momentum_decay))) for step in state_steps]
    mu_nexts = [beta1 * (1. - 0.5 * (0.96 ** ((step.item() + 1) * momentum_decay)))
                for step in state_steps]

    # update mu_products
    torch._foreach_mul_(mu_products, mus)

    if weight_decay != 0:
        torch._foreach_add_(grads, params, alpha=weight_decay)

    # Decay the first and second moment running average coefficient
    torch._foreach_mul_(exp_avg, beta1)
    torch._foreach_add_(exp_avg, grads, alpha=1 - beta1)

    torch._foreach_mul_(exp_avg_sq, beta2)
    torch._foreach_addcmul_(exp_avg_sq, grads, grads, 1 - beta2)

    exp_avg_sq_sqrt = torch._foreach_sqrt(exp_avg_sq)
    bias_correction_sqrt = [math.sqrt(bc) for bc in bias_correction2]
    torch._foreach_div_(exp_avg_sq_sqrt, bias_correction_sqrt)
    denom = torch._foreach_add(exp_avg_sq_sqrt, eps)

    step_size_grads = [(lr * (1. - mu) / (1. - mu_product.item())) * -1
                       for mu_product, mu in zip(mu_products, mus)]
    step_size_expavg = [(lr * mu_next / (1. - mu_product.item() * mu_next)) * -1
                        for mu_product, mu_next in zip(mu_products, mu_nexts)]
    torch._foreach_addcdiv_(params, grads, denom, step_size_grads)
    torch._foreach_addcdiv_(params, exp_avg, denom, step_size_expavg)
