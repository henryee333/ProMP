import os
import json
import tensorflow as tf
import numpy as np
from experiment_utils.run_sweep import run_sweep
from meta_policy_search.utils.utils import set_seed, ClassEncoder
from meta_policy_search.baselines.linear_baseline import LinearTimeBaseline, LinearFeatureBaseline
from meta_policy_search.envs.mujoco_envs.half_cheetah_rand_direc import HalfCheetahRandDirecEnv
from meta_policy_search.envs.normalized_env import normalize
from experiments.gradient_variance.vpg_dice_maml_extract_grads import VPG_DICEMAML
from experiments.gradient_variance.vpg_maml_extract_grads import VPGMAML
from experiments.gradient_variance.dice_maml_extract_grads import DICEMAML
from experiments.gradient_variance.meta_trainer_gradient_variance import TrainerGradientStd
from meta_policy_search.samplers.maml_sampler import MAMLSampler
from meta_policy_search.samplers import DiceMAMLSampleProcessor, MAMLSampleProcessor
from meta_policy_search.policies.meta_gaussian_mlp_policy import MetaGaussianMLPPolicy
from meta_policy_search.utils import logger

INSTANCE_TYPE = 'c4.4xlarge'
EXP_NAME = 'gradient_variance_v2'

def run_experiment(**kwargs):
    exp_dir = os.getcwd() + '/data/' + EXP_NAME
    logger.configure(dir=exp_dir, format_strs=['stdout', 'log', 'csv'], snapshot_mode='last_gap', snapshot_gap=50)
    json.dump(kwargs, open(exp_dir + '/params.json', 'w'), indent=2, sort_keys=True, cls=ClassEncoder)

    # Instantiate classes
    set_seed(kwargs['seed'])

    env = normalize(kwargs['env']()) # Wrappers?

    policy = MetaGaussianMLPPolicy(
        name="meta-policy",
        obs_dim=np.prod(env.observation_space.shape),
        action_dim=np.prod(env.action_space.shape),
        meta_batch_size=kwargs['meta_batch_size'],
        hidden_sizes=kwargs['hidden_sizes'],
        learn_std=kwargs['learn_std'],
        hidden_nonlinearity=kwargs['hidden_nonlinearity'],
        output_nonlinearity=kwargs['output_nonlinearity'],
    )

    # Load policy here

    sampler = MAMLSampler(
        env=env,
        policy=policy,
        rollouts_per_meta_task=kwargs['rollouts_per_meta_task'],
        meta_batch_size=kwargs['meta_batch_size'],
        max_path_length=kwargs['max_path_length'],
        parallel=kwargs['parallel'],
        envs_per_task=int(kwargs['rollouts_per_meta_task'])
    )

    if kwargs['algo'] == 'DICE':
        sample_processor = DiceMAMLSampleProcessor(
            baseline=LinearTimeBaseline(),
            max_path_length=kwargs['max_path_length'],
            discount=kwargs['discount'],
            normalize_adv=kwargs['normalize_adv'],
            positive_adv=kwargs['positive_adv'],
        )

        algo = DICEMAML(
            policy=policy,
            max_path_length=kwargs['max_path_length'],
            meta_batch_size=kwargs['meta_batch_size'],
            num_inner_grad_steps=kwargs['num_inner_grad_steps'],
            inner_lr=kwargs['inner_lr'],
            learning_rate=kwargs['learning_rate']
        )

    elif kwargs['algo'] == 'VPG_DICE':
        sample_processor = DiceMAMLSampleProcessor(
            baseline=LinearTimeBaseline(),
            max_path_length=kwargs['max_path_length'],
            discount=kwargs['discount'],
            normalize_adv=kwargs['normalize_adv'],
            positive_adv=kwargs['positive_adv'],
            return_baseline=LinearFeatureBaseline()
        )

        algo = VPG_DICEMAML(
            policy=policy,
            max_path_length=kwargs['max_path_length'],
            meta_batch_size=kwargs['meta_batch_size'],
            num_inner_grad_steps=kwargs['num_inner_grad_steps'],
            inner_lr=kwargs['inner_lr'],
            learning_rate=kwargs['learning_rate']
        )

    elif kwargs['algo'] == 'VPG':
        sample_processor = MAMLSampleProcessor(
            baseline=LinearFeatureBaseline(),
            discount=kwargs['discount'],
            normalize_adv=kwargs['normalize_adv'],
            positive_adv=kwargs['positive_adv'],
        )

        algo = VPGMAML(
            policy=policy,
            meta_batch_size=kwargs['meta_batch_size'],
            num_inner_grad_steps=kwargs['num_inner_grad_steps'],
            inner_type='likelihood_ratio',
            inner_lr=kwargs['inner_lr'],
            learning_rate=kwargs['learning_rate']
        )

    trainer = TrainerGradientStd(
        algo=algo,
        policy=policy,
        env=env,
        sampler=sampler,
        sample_processor=sample_processor,
        n_itr=kwargs['n_itr'],
        num_inner_grad_steps=kwargs['num_inner_grad_steps'],
        num_sapling_rounds=kwargs['sampling_rounds']
    )

    trainer.train()

if __name__ == '__main__':    

    sweep_params = {
        'seed': [35, 76, 34, 92],

        'algo': ['VPG_DICE', 'VPG'],

        'sampling_rounds': [10],

        'env': [HalfCheetahRandDirecEnv],

        'rollouts_per_meta_task': [40],
        'max_path_length': [100],
        'parallel': [True],

        'discount': [0.99],
        'normalize_adv': [True],
        'positive_adv': [False],

        'hidden_sizes': [(64, 64)],
        'learn_std': [True],
        'hidden_nonlinearity': [tf.tanh],
        'output_nonlinearity': [None],

        'inner_lr': [0.1],
        'learning_rate': [1e-3],

        'n_itr': [301],
        'meta_batch_size': [20],
        'num_inner_grad_steps': [1],
        'scope': [None],
    }
        
    run_sweep(run_experiment, sweep_params, EXP_NAME, INSTANCE_TYPE)